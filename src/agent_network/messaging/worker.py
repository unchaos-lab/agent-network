"""RabbitMQ worker — task event processor.

Two usage modes sharing the same ``process_message()`` core logic:

* **Local (Docker Compose)** — ``start_worker()`` runs a long-lived
  RabbitMQ consumer.  Scale with ``docker compose up --scale worker=N``.
* **Cloud (serverless)** — ``worker_main.py`` calls ``process_message()``
  once per invocation and exits (Lambda, Cloud Run, etc.).
"""

from __future__ import annotations

import json
import logging
from typing import Any

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

from agent_network.config import Settings

logger = logging.getLogger(__name__)


# ── shared processing logic ───────────────────────────────────────


async def process_message(event: str, data: dict[str, Any]) -> None:
    """Process a single task event.

    **This is the placeholder** — replace this body with real
    agent / AI logic as needed.

    Parameters
    ----------
    event:
        The event type, e.g. ``"task.created"``.
    data:
        The deserialized event payload.
    """
    logger.info(
        "Worker processing event: %s | payload keys: %s",
        event,
        list(data.keys()),
    )
    # TODO: Add real processing logic here.
    # For example: trigger an AI agent, update external systems, etc.


def parse_payload(raw: str) -> tuple[str, dict[str, Any]]:
    """Decode and parse a JSON payload string.

    Returns
    -------
    tuple[str, dict]
        ``(event, data)`` extracted from the message.
    """
    body: dict[str, Any] = json.loads(raw)
    event = body.get("event", "unknown")
    data = body.get("data", {})
    return event, data


# ── long-running consumer (local / Docker Compose) ───────────────


async def _on_message(message: AbstractIncomingMessage) -> None:
    """Callback invoked for each message delivered by RabbitMQ."""
    async with message.process():
        try:
            event, data = parse_payload(message.body.decode())
        except Exception:
            logger.error("Worker received unparseable message — skipping")
            return

        try:
            await process_message(event, data)
        except Exception:
            logger.exception("Unhandled error while processing event %s", event)


async def start_worker(settings: Settings) -> None:
    """Connect to RabbitMQ and start consuming messages.

    This coroutine runs **indefinitely** (until cancelled) and is
    designed to be launched as a long-running container.
    """
    logger.info("Worker connecting to RabbitMQ at %s …", settings.rabbitmq_url)

    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel = await connection.channel()

    exchange = await channel.declare_exchange(
        settings.rabbitmq_exchange,
        aio_pika.ExchangeType.TOPIC,
        durable=True,
    )

    queue = await channel.declare_queue(
        settings.rabbitmq_task_queue,
        durable=True,
    )
    await queue.bind(exchange, routing_key="task.#")

    # Prefetch 1 message at a time for fair dispatch across replicas
    await channel.set_qos(prefetch_count=1)

    logger.info(
        "Worker listening on queue '%s' (exchange=%s)",
        settings.rabbitmq_task_queue,
        settings.rabbitmq_exchange,
    )
    await queue.consume(_on_message)
