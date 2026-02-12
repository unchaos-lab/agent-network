"""Webhook registration and lifecycle management against Light-Tasks.

Handles the full signup flow: authenticate with the API, clean up any
previous registrations, and create a fresh webhook — returning the HMAC
secret that the consumer needs to verify incoming deliveries.
"""

from __future__ import annotations

import logging

from agent_network.api.client import LightTasksClient
from agent_network.config import Settings

logger = logging.getLogger(__name__)


class WebhookRegistry:
    """Sign up for Light-Tasks webhook notifications.

    The registry owns the entire signup lifecycle:

    1. **Login** — obtain a JWT token so the API accepts our requests.
    2. **Cleanup** — remove stale webhooks that point to our callback URL.
    3. **Register** — create a new webhook and capture the HMAC secret.

    Parameters
    ----------
    api_client:
        ``LightTasksClient`` instance (token will be set after login).
    settings:
        Application settings (credentials, callback URL, events, …).
    """

    def __init__(self, api_client: LightTasksClient, settings: Settings) -> None:
        self._api = api_client
        self._settings = settings

    # ── Public API ──────────────────────────────────────────────────

    def signup(self) -> str:
        """Run the full signup flow and return the webhook **secret**.

        Returns
        -------
        str
            The HMAC-SHA256 secret for verifying incoming deliveries.
        """
        self._login()
        self._cleanup_old_webhooks()
        return self._register()

    # ── Internal steps ──────────────────────────────────────────────

    def _login(self) -> None:
        """Authenticate against Light-Tasks and store the token."""
        email = self._settings.admin_email
        logger.info("Logging in to Light-Tasks as %s …", email)

        response = self._api.post(
            "/auth/login",
            json={
                "email": email,
                "password": self._settings.admin_password,
            },
        )
        token = response.json()["access_token"]
        self._api.set_token(token)
        logger.info("Authenticated (token …%s)", token[-8:])

    def _cleanup_old_webhooks(self) -> None:
        """Delete any existing webhooks that point to our callback URL."""
        callback = self._settings.webhook_callback_url
        logger.info("Cleaning up old webhooks pointing to %s", callback)

        try:
            response = self._api.get("/webhooks")
            webhooks = response.json().get("data", [])
            for wh in webhooks:
                if wh.get("url") == callback:
                    wh_id = wh["id"]
                    logger.info("Deleting stale webhook %s", wh_id)
                    self._api.delete(f"/webhooks/{wh_id}")
        except Exception:
            logger.warning("Could not clean up old webhooks", exc_info=True)

    def _register(self) -> str:
        """Register a new webhook and return the HMAC secret."""
        callback = self._settings.webhook_callback_url
        events = self._settings.webhook_events_list
        logger.info("Registering webhook → %s  events=%s", callback, events)

        response = self._api.post(
            "/webhooks",
            json={
                "url": callback,
                "events": events,
            },
        )
        data = response.json()
        secret: str = data["secret"]
        webhook_id: str = data["id"]

        logger.info("Webhook registered  id=%s", webhook_id)
        return secret
