"""Worker entry-point — supports two modes.

Local (Docker Compose)
    ``agent-network-worker`` with no ``TASK_PAYLOAD`` env var starts a
    **long-running** RabbitMQ consumer.  Scale with
    ``docker compose up --scale worker=N``.

Cloud (serverless)
    Set ``TASK_PAYLOAD`` (base64-encoded JSON) and the process handles
    **one** message then exits — ideal for Lambda, Cloud Run, etc.

Exit codes:
    0 — success
    1 — error (logged)
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import sys

from agent_network.config import get_settings
from agent_network.messaging.worker import parse_payload, process_message, start_worker

logger = logging.getLogger(__name__)


def _setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ── serverless (one-shot) mode ─────────────────────────────────


async def _run_oneshot() -> None:
    raw_b64 = os.getenv("TASK_PAYLOAD", "")

    try:
        raw = base64.b64decode(raw_b64).decode()
    except Exception:
        logger.exception("Failed to base64-decode TASK_PAYLOAD")
        sys.exit(1)

    try:
        event, data = parse_payload(raw)
    except Exception:
        logger.exception("Failed to parse payload JSON")
        sys.exit(1)

    logger.info("One-shot worker processing event: %s", event)

    try:
        await process_message(event, data)
    except Exception:
        logger.exception("Error processing event %s", event)
        sys.exit(1)

    logger.info("One-shot worker finished")


# ── long-running mode (Docker Compose) ────────────────────────


async def _run_consumer() -> None:
    settings = get_settings()
    logger.info("Starting long-running worker …")

    await start_worker(settings)

    # Keep the event loop alive until interrupted
    stop = asyncio.Event()

    import signal

    def _signal_handler() -> None:
        logger.info("Shutdown signal received")
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    await stop.wait()
    logger.info("Worker shut down cleanly")


# ── entry-point ───────────────────────────────────────────


async def _run() -> None:
    _setup_logging(os.getenv("LOG_LEVEL", "INFO"))

    if os.getenv("TASK_PAYLOAD"):
        # Serverless / one-shot mode
        await _run_oneshot()
    else:
        # Long-running consumer mode (default for Docker Compose)
        await _run_consumer()


def main() -> None:
    """CLI entry-point."""
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
