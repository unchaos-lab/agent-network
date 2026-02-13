"""CRUD service for agent configuration stored in Redis.

Each agent's config is stored as a JSON hash under the key
``agent:config:{agent_id}``.  Redis is configured with AOF persistence
so data survives restarts.

Usage
-----
    from agent_network.store import AgentConfigStore
    from agent_network.config import get_settings

    store = AgentConfigStore(get_settings().redis_url)

    # Create / update
    store.set("agent-42", {"system_prompt": "You are a helpful assistant."})

    # Read
    config = store.get("agent-42")

    # Delete
    store.delete("agent-42")
"""

from __future__ import annotations

import json
import logging
from typing import Any

import redis

logger = logging.getLogger(__name__)

_KEY_PREFIX = "agent:config"


def _key(agent_id: str) -> str:
    return f"{_KEY_PREFIX}:{agent_id}"


class AgentConfigStore:
    """Synchronous Redis-backed agent configuration store."""

    def __init__(self, redis_url: str) -> None:
        self._client = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
        )

    # ── CRUD ──────────────────────────────────────────────────────

    def set(self, agent_id: str, config: dict[str, Any]) -> None:
        """Create or fully replace the config for *agent_id*."""
        self._client.set(_key(agent_id), json.dumps(config))
        logger.info("Stored config for agent %s", agent_id)

    def get(self, agent_id: str) -> dict[str, Any] | None:
        """Return the config dict for *agent_id*, or ``None``."""
        raw = self._client.get(_key(agent_id))
        if raw is None:
            return None
        return json.loads(raw)

    def update(self, agent_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        """Merge *patch* into the existing config for *agent_id*.

        Creates the key if it doesn't exist yet.
        Returns the updated config.
        """
        current = self.get(agent_id) or {}
        current.update(patch)
        self.set(agent_id, current)
        return current

    def delete(self, agent_id: str) -> bool:
        """Delete the config for *agent_id*.  Returns ``True`` if it existed."""
        removed = self._client.delete(_key(agent_id))
        return removed > 0

    def exists(self, agent_id: str) -> bool:
        """Check whether a config exists for *agent_id*."""
        return self._client.exists(_key(agent_id)) > 0

    def list_agents(self) -> list[str]:
        """Return all agent IDs that have a stored config."""
        prefix = f"{_KEY_PREFIX}:"
        keys = self._client.keys(f"{prefix}*")
        return [k.removeprefix(prefix) for k in keys]

    def get_system_prompt(self, agent_id: str) -> str | None:
        """Convenience: return only the ``system_prompt`` field, or ``None``."""
        config = self.get(agent_id)
        if config is None:
            return None
        return config.get("system_prompt")

    # ── lifecycle ─────────────────────────────────────────────────

    def ping(self) -> bool:
        """Return ``True`` if Redis is reachable."""
        try:
            return self._client.ping()
        except redis.ConnectionError:
            return False

    def close(self) -> None:
        """Close the underlying Redis connection."""
        self._client.close()
