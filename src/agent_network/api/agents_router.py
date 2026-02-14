"""REST API router for agent configuration CRUD.

Provides endpoints to list, get, create, update, and delete agent
configurations stored in Redis.  The create endpoint optionally
provisions the agent as a user in Light-Tasks and stores the returned
API key alongside the system prompt.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from agent_network.config import get_settings
from agent_network.store import AgentConfigStore
from agent_network.api.client import LightTasksClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])


# ── Request / response schemas ────────────────────────────────────────────

class AgentConfigResponse(BaseModel):
    agent_id: str
    name: str = ""
    system_prompt: str = ""
    api_key: str = ""


class AgentConfigCreate(BaseModel):
    """Body for creating a new agent config."""

    name: str = Field(..., min_length=1, description="Agent display name (used when creating the user in Light-Tasks)")
    system_prompt: str = Field("", description="System prompt for the LLM")
    agent_id: str | None = Field(None, description="Optional custom UUID; auto-generated when omitted")


class AgentConfigUpdate(BaseModel):
    """Body for partially updating an existing agent config."""

    name: str | None = None
    system_prompt: str | None = None


# ── Helpers ───────────────────────────────────────────────────────────────

def _get_store() -> AgentConfigStore:
    return AgentConfigStore(get_settings().redis_url)


def _config_to_response(agent_id: str, config: dict[str, Any]) -> AgentConfigResponse:
    return AgentConfigResponse(
        agent_id=agent_id,
        name=config.get("name", ""),
        system_prompt=config.get("system_prompt", ""),
        api_key=config.get("api_key", ""),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("", response_model=list[AgentConfigResponse])
def list_agents():
    """Return every agent configuration stored in Redis."""
    store = _get_store()
    agent_ids = store.list_agents()
    results: list[AgentConfigResponse] = []
    for aid in sorted(agent_ids):
        cfg = store.get(aid)
        if cfg is not None:
            results.append(_config_to_response(aid, cfg))
    return results


@router.get("/{agent_id}", response_model=AgentConfigResponse)
def get_agent(agent_id: str):
    """Return the config for a single agent."""
    store = _get_store()
    cfg = store.get(agent_id)
    if cfg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return _config_to_response(agent_id, cfg)


@router.post("", response_model=AgentConfigResponse, status_code=status.HTTP_201_CREATED)
def create_agent(body: AgentConfigCreate):
    """Create a new agent.

    1. Provisions an agent-type user in Light-Tasks (returns an API key).
    2. Stores ``{system_prompt, api_key, name}`` in Redis keyed by the
       Light-Tasks user ID so the worker can look it up by ``responsible.id``.
    """
    store = _get_store()

    # Provision agent user in Light-Tasks to obtain an API key
    settings = get_settings()
    api_key = ""
    lt_user_id = ""
    try:
        # Authenticate as admin to create the agent user
        client = LightTasksClient(settings)
        login_resp = client.post(
            "/auth/login",
            json={"email": settings.admin_email, "password": settings.admin_password},
        )
        token = login_resp.json()["access_token"]
        client.set_token(token)

        user_resp = client.post("/users", json={"type": "agent", "name": body.name})
        user_data = user_resp.json()
        api_key = user_data.get("api_key", "")
        lt_user_id = user_data.get("id", "")
        logger.info("Provisioned Light-Tasks agent user %s (id=%s)", body.name, lt_user_id)
    except Exception:
        logger.exception("Failed to provision agent user in Light-Tasks — storing config without API key")

    # Use the Light-Tasks user ID as the Redis key so the worker
    # (which looks up by responsible.id) can find the config.
    agent_id = lt_user_id or body.agent_id or str(uuid.uuid4())

    if store.exists(agent_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Agent {agent_id} already exists",
        )

    config = {
        "name": body.name,
        "system_prompt": body.system_prompt,
        "api_key": api_key,
        "light_tasks_user_id": lt_user_id,
    }
    store.set(agent_id, config)

    return _config_to_response(agent_id, config)


@router.patch("/{agent_id}", response_model=AgentConfigResponse)
def update_agent(agent_id: str, body: AgentConfigUpdate):
    """Partially update an agent's configuration (system_prompt, name)."""
    store = _get_store()
    if not store.exists(agent_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    patch: dict[str, Any] = {}
    if body.system_prompt is not None:
        patch["system_prompt"] = body.system_prompt
    if body.name is not None:
        patch["name"] = body.name

    updated = store.update(agent_id, patch)
    return _config_to_response(agent_id, updated)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(agent_id: str):
    """Delete an agent configuration from Redis."""
    store = _get_store()
    if not store.delete(agent_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return None
