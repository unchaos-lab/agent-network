"""Startup orchestrator — health-check, webhook signup, RabbitMQ, and serve."""

from __future__ import annotations

import logging
import sys
import time
from contextlib import asynccontextmanager

import httpx
import uvicorn

from agent_network.api.client import LightTasksClient
from agent_network.config import Settings, get_settings
from agent_network.messaging.publisher import RabbitPublisher
from agent_network.webhook.consumer import create_consumer_app
from agent_network.webhook.registry import WebhookRegistry

logger = logging.getLogger(__name__)


def _wait_for_api(settings: Settings) -> None:
    """Block until the Light-Tasks API is fully ready (health endpoint)."""
    health_url = f"{settings.api_base_url}/health"
    logger.info("Waiting for Light-Tasks API at %s …", settings.api_base_url)

    for attempt in range(1, settings.max_retries + 1):
        try:
            response = httpx.get(health_url, timeout=5)
            response.raise_for_status()
            logger.info("API is up (attempt %d)", attempt)
            return
        except Exception:
            logger.debug("Attempt %d/%d — not ready yet", attempt, settings.max_retries)
            time.sleep(settings.retry_interval)

    logger.critical("API did not become ready in time. Exiting.")
    sys.exit(1)


def _setup_logging(level: str) -> None:
    """Configure root logger with a human-friendly format."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> None:
    """Entry-point: wait for API, sign up for webhooks, then serve."""
    settings = get_settings()
    _setup_logging(settings.log_level)

    logger.info("Agent Network starting …")

    # 1. Wait for Light-Tasks API
    _wait_for_api(settings)

    # 2. Sign up for webhooks (login → cleanup → register)
    api_client = LightTasksClient(settings)
    registry = WebhookRegistry(api_client, settings)

    for attempt in range(1, settings.max_retries + 1):
        try:
            secret = registry.signup()
            break
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401 and attempt < settings.max_retries:
                logger.warning(
                    "Login attempt %d/%d failed (401) — admin user may not exist yet, retrying …",
                    attempt,
                    settings.max_retries,
                )
                time.sleep(settings.retry_interval)
                continue
            logger.critical(
                "Webhook signup failed (%s): %s",
                exc.response.status_code,
                exc.response.text,
            )
            sys.exit(1)

    # 3. Start the consumer server (worker runs in separate containers)
    publisher = RabbitPublisher(settings)

    @asynccontextmanager
    async def _lifespan(app):  # noqa: ANN001
        """Connect publisher on startup; clean up on shutdown."""
        await publisher.connect()
        logger.info("RabbitMQ publisher connected")
        yield
        await publisher.close()

    app = create_consumer_app(secret=secret, publisher=publisher)
    app.router.lifespan_context = _lifespan

    logger.info(
        "Starting webhook consumer on %s:%d",
        settings.webhook_host,
        settings.webhook_port,
    )
    uvicorn.run(
        app,
        host=settings.webhook_host,
        port=settings.webhook_port,
        log_level=settings.log_level.lower(),
    )
