"""RabbitMQ message publisher (sender service).

Provides a thin async wrapper around *aio-pika* for publishing
task-event messages to a RabbitMQ exchange.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import aio_pika

from agent_network.config import Settings

logger = logging.getLogger(__name__)


class RabbitPublisher:
    """Publishes JSON messages to RabbitMQ."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._exchange: aio_pika.abc.AbstractExchange | None = None

    # ── lifecycle ──────────────────────────────────────────────

    async def connect(self) -> None:
        """Establish a robust connection and declare the exchange + queue."""
        logger.info("Connecting to RabbitMQ at %s …", self._settings.rabbitmq_url)

        self._connection = await aio_pika.connect_robust(self._settings.rabbitmq_url)
        self._channel = await self._connection.channel()

        # Declare a durable topic exchange
        self._exchange = await self._channel.declare_exchange(
            self._settings.rabbitmq_exchange,
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )

        # Declare the task-events queue and bind it
        queue = await self._channel.declare_queue(
            self._settings.rabbitmq_task_queue,
            durable=True,
        )
        await queue.bind(self._exchange, routing_key="task.#")

        logger.info(
            "RabbitMQ publisher ready (exchange=%s, queue=%s)",
            self._settings.rabbitmq_exchange,
            self._settings.rabbitmq_task_queue,
        )

    async def close(self) -> None:
        """Gracefully close the RabbitMQ connection."""
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
            logger.info("RabbitMQ publisher connection closed")

    # ── publishing ─────────────────────────────────────────────

    async def publish(
        self,
        routing_key: str,
        body: dict[str, Any],
    ) -> None:
        """Serialize *body* as JSON and publish it to the exchange.

        Parameters
        ----------
        routing_key:
            The AMQP routing key (e.g. ``"task.created"``).
        body:
            A JSON-serializable dictionary to send as the message body.
        """
        if self._exchange is None:
            raise RuntimeError("Publisher is not connected — call connect() first")

        message = aio_pika.Message(
            body=json.dumps(body, default=str).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )

        await self._exchange.publish(message, routing_key=routing_key)
        logger.info("Published message with routing_key=%s", routing_key)
