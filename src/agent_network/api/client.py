"""Low-level HTTP client for the Light-Tasks REST API."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from agent_network.config import Settings

logger = logging.getLogger(__name__)


class LightTasksClient:
    """Thin wrapper around *httpx* for talking to the Light-Tasks API.

    Parameters
    ----------
    settings:
        Application settings (base URL, prefix, timeouts …).
    token:
        Optional JWT bearer token to include in every request.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        token: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._base = f"{settings.api_base_url}{settings.api_prefix}"
        self._token = token
        self._api_key = api_key
        self._timeout = httpx.Timeout(10.0)

    # ── Public helpers ──────────────────────────────────────────────

    def set_token(self, token: str) -> None:
        """Update the bearer token used for authenticated requests."""
        self._token = token

    def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Execute an HTTP request and return the *httpx.Response*.

        Raises
        ------
        httpx.HTTPStatusError
            If the response status code indicates an error (4xx / 5xx).
        """
        url = f"{self._base}{path}"
        headers: dict[str, str] = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        elif self._api_key:
            headers["X-API-Key"] = self._api_key

        logger.debug("%s %s", method, url)

        response = httpx.request(
            method,
            url,
            json=json,
            headers=headers,
            timeout=self._timeout,
        )
        response.raise_for_status()
        return response

    # ── Convenience shortcuts ───────────────────────────────────────

    def get(self, path: str) -> httpx.Response:
        return self.request("GET", path)

    def post(self, path: str, *, json: dict[str, Any] | None = None) -> httpx.Response:
        return self.request("POST", path, json=json)

    def patch(self, path: str, *, json: dict[str, Any] | None = None) -> httpx.Response:
        return self.request("PATCH", path, json=json)

    def delete(self, path: str) -> httpx.Response:
        return self.request("DELETE", path)
