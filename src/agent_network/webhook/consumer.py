"""FastAPI-based HTTP server that receives webhook events from Light-Tasks."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request, status

from agent_network.api.agents_router import router as agents_router
from agent_network.messaging.publisher import RabbitPublisher
from agent_network.webhook.signature import verify_signature

logger = logging.getLogger(__name__)

# Events that should be forwarded to RabbitMQ
_TASK_EVENTS = frozenset({
    "task.created",
    "task.updated",
    "task.deleted",
    "task.moved",
    "task.commented",
    "task.feedback_added",
})


def create_consumer_app(
    *,
    secret: str | None = None,
    publisher: RabbitPublisher | None = None,
) -> FastAPI:
    """Build and return a :class:`FastAPI` application for consuming webhooks.

    Parameters
    ----------
    secret:
        The HMAC secret returned when the webhook was registered.
        When ``None`` signature verification is skipped (not recommended).
    publisher:
        An optional :class:`RabbitPublisher` instance.  When provided,
        task events are forwarded to RabbitMQ.
    """
    app = FastAPI(title="Agent Network — Webhook Consumer")

    # ── CORS for frontend access ──────────────────────────────────
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Mount agents CRUD router ──────────────────────────────────
    app.include_router(agents_router)

    # Store the secret on the app so middleware / routes can access it.
    app.state.webhook_secret = secret
    app.state.publisher = publisher

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Simple liveness probe."""
        return {"status": "ok"}

    @app.post("/webhook")
    async def receive_webhook(
        request: Request,
        x_webhook_signature: str | None = Header(default=None),
        x_webhook_event: str | None = Header(default=None),
    ) -> dict[str, str]:
        """Handle an incoming webhook delivery from Light-Tasks."""
        raw_body = await request.body()

        # ── Signature verification ────────────────────────────────
        wh_secret = request.app.state.webhook_secret
        if wh_secret:
            if not x_webhook_signature:
                logger.warning("Rejected webhook: missing signature header")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing signature header",
                )
            if not verify_signature(raw_body, wh_secret, x_webhook_signature):
                logger.warning("Rejected webhook: invalid signature")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid signature",
                )

        # ── Parse payload ─────────────────────────────────────────
        try:
            payload: dict[str, Any] = json.loads(raw_body)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON body",
            )

        event = payload.get("event", x_webhook_event or "unknown")
        data = payload.get("data", {})

        _log_event(event, data)

        # ── Forward task events to RabbitMQ ───────────────────────
        pub: RabbitPublisher | None = request.app.state.publisher
        if pub and event in _TASK_EVENTS:
            await pub.publish(routing_key=event, body=payload)

        return {"status": "received"}

    return app


def _log_event(event: str, data: dict[str, Any]) -> None:
    """Pretty-print an incoming webhook event to the log."""
    logger.info(
        "Webhook event received: %s\n%s",
        event,
        json.dumps(data, indent=2, default=str),
    )
