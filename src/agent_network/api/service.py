"""High-level service for interacting with the Light-Tasks REST API.

All methods authenticate using an agent API key (``X-API-Key`` header).
The key is read from the ``AGENT_API_KEY`` environment variable
(or ``.env`` file).
"""

from __future__ import annotations

import logging
from typing import Any

from agent_network.api.client import LightTasksClient
from agent_network.config import Settings

logger = logging.getLogger(__name__)


class LightTasksService:
    """Domain-oriented facade over :class:`LightTasksClient`.

    Parameters
    ----------
    client:
        A :class:`LightTasksClient` already configured with an API key.
    """

    def __init__(self, client: LightTasksClient) -> None:
        self._client = client

    # ── Factory ─────────────────────────────────────────────────────

    @classmethod
    def from_settings(cls, settings: Settings) -> LightTasksService:
        """Build a service instance from application settings."""
        if not settings.agent_api_key:
            raise RuntimeError(
                "AGENT_API_KEY is not set. "
                "Create an agent user in Light-Tasks and put the returned "
                "API key in the .env file."
            )
        client = LightTasksClient(settings, api_key=settings.agent_api_key)
        return cls(client)

    # ── Tasks ───────────────────────────────────────────────────────

    def create_task(
        self,
        *,
        table: str = "backlog",
        responsible_id: str,
        description: str,
        reviewer_id: str | None = None,
        output_expected: str | None = None,
        acceptance_criteria: list[str] | None = None,
        supplements: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Create a new task.

        Returns the full ``TaskRead`` payload from the API.
        """
        body: dict[str, Any] = {
            "table": table,
            "responsible_id": responsible_id,
            "description": description,
        }
        if reviewer_id is not None:
            body["reviewer_id"] = reviewer_id
        if output_expected is not None:
            body["output_expected"] = output_expected
        if acceptance_criteria is not None:
            body["acceptance_criteria"] = acceptance_criteria
        if supplements is not None:
            body["supplements"] = supplements

        resp = self._client.post("/tasks", json=body)
        logger.info("Created task %s", resp.json().get("id"))
        return resp.json()

    def update_task(
        self,
        task_id: str,
        **fields: Any,
    ) -> dict[str, Any]:
        """Partially update a task.

        Accepted keyword arguments mirror the ``TaskUpdate`` schema:
        ``table``, ``responsible_id``, ``reviewer_id``, ``description``,
        ``output_expected``, ``acceptance_criteria``, ``supplements``.

        Returns the updated ``TaskRead`` payload.
        """
        resp = self._client.patch(f"/tasks/{task_id}", json=fields)
        logger.info("Updated task %s", task_id)
        return resp.json()

    def move_task(self, task_id: str, table: str) -> dict[str, Any]:
        """Move a task to a different table / column.

        Returns the updated ``TaskRead`` payload.
        """
        resp = self._client.post(
            f"/tasks/{task_id}/move",
            json={"table": table},
        )
        logger.info("Moved task %s → %s", task_id, table)
        return resp.json()

    def mark_task_done(self, task_id: str) -> dict[str, Any]:
        """Convenience shortcut to move a task to the ``done`` table."""
        return self.move_task(task_id, "done")

    # ── Comments ────────────────────────────────────────────────────

    def add_comment(self, task_id: str, content: str) -> dict[str, Any]:
        """Add a comment to a task.

        Returns the ``CommentRead`` payload.
        """
        resp = self._client.post(
            f"/tasks/{task_id}/comments",
            json={"content": content},
        )
        logger.info("Added comment to task %s", task_id)
        return resp.json()

    # ── Feedback ────────────────────────────────────────────────────

    def add_feedback(
        self,
        task_id: str,
        rating: int,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Add feedback to a completed (done) task.

        Parameters
        ----------
        task_id:
            UUID of the task (must already be in ``done``).
        rating:
            Score from 1 to 5.
        comment:
            Optional textual feedback.

        Returns the updated ``TaskRead`` payload.
        """
        body: dict[str, Any] = {"rating": rating}
        if comment is not None:
            body["comment"] = comment

        resp = self._client.post(f"/tasks/{task_id}/feedback", json=body)
        logger.info("Added feedback (rating=%d) to task %s", rating, task_id)
        return resp.json()

    # ── Users ───────────────────────────────────────────────────────

    def create_agent_user(self, name: str) -> dict[str, Any]:
        """Create a new **agent** type user.

        Returns the ``UserCreateRead`` payload which includes the
        one-time ``api_key`` field.
        """
        resp = self._client.post(
            "/users",
            json={"type": "agent", "name": name},
        )
        data = resp.json()
        logger.info(
            "Created agent user '%s' (id=%s)",
            name,
            data.get("id"),
        )
        return data
