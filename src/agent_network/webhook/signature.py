"""HMAC-SHA256 signature verification for incoming webhooks."""

from __future__ import annotations

import hashlib
import hmac
import logging

logger = logging.getLogger(__name__)


def verify_signature(payload: bytes, secret: str, received_signature: str) -> bool:
    """Verify the ``X-Webhook-Signature`` header sent by Light-Tasks.

    Parameters
    ----------
    payload:
        Raw request body bytes.
    secret:
        The webhook secret returned at registration time.
    received_signature:
        Value of the ``X-Webhook-Signature`` header (``sha256=…``).

    Returns
    -------
    bool
        ``True`` when the signature is valid.
    """
    expected = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    expected_full = f"sha256={expected}"
    is_valid = hmac.compare_digest(expected_full, received_signature)

    if not is_valid:
        logger.warning("Signature verification failed")

    return is_valid
