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

from agent_network.api.service import LightTasksService
from agent_network.config import Settings, get_settings
from agent_network.agents.worker.main import execute_worker_agent

logger = logging.getLogger(__name__)

_service: LightTasksService | None = None


def _get_service() -> LightTasksService:
    """Return a lazily-initialised LightTasksService singleton."""
    global _service  # noqa: PLW0603
    if _service is None:
        _service = LightTasksService.from_settings(get_settings())
    return _service


# ── shared processing logic ───────────────────────────────────────


async def process_message(event: str, data: dict[str, Any]) -> None:
    """Process a single task event.

    Only reacts to ``task.created`` — marks the new task as **done**
    via the Light-Tasks API.  All other events are logged and ignored
    to avoid feedback loops (e.g. ``task.moved`` → move → ``task.moved`` …).

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

    if event != "task.created":
        logger.debug("Ignoring event %s — not actionable", event)
        return

    task_id: str | None = data.get("id") or data.get("task_id")
    if not task_id:
        logger.warning("No task id found in payload — skipping")
        return

    service = _get_service()
    try:
        task = execute_worker_agent(data.get("description", ""))
        service.add_comment(task_id, task)
        service.mark_task_done(task_id)
        logger.info("Task %s marked as done", task_id)
    except Exception:
        logger.exception("Failed to mark task %s as done", task_id)


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
