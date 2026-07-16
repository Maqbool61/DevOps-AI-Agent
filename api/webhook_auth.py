"""
Webhook and Slack request signature verification.
"""
import hashlib
import hmac
import os
import time
from typing import Optional


def verify_hmac_sha256_signature(payload: bytes, signature: str, secret: str) -> bool:
    if not secret or not signature:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def get_webhook_secret() -> str:
    return os.getenv("WEBHOOK_SECRET", "")


def verify_webhook_request(payload: bytes, signature: Optional[str]) -> bool:
    """Verify webhook using WEBHOOK_SECRET and X-Hub-Signature-256 / X-Webhook-Signature."""
    secret = get_webhook_secret()
    if not secret:
        return True
    if not signature:
        return False
    return verify_hmac_sha256_signature(payload, signature, secret)


def get_slack_signing_secret() -> str:
    return os.getenv("SLACK_SIGNING_SECRET", "")


def verify_slack_signature(
    body: bytes,
    timestamp: Optional[str],
    signature: Optional[str],
    signing_secret: Optional[str] = None,
    max_age_seconds: int = 300,
) -> bool:
    secret = signing_secret or get_slack_signing_secret()
    if not secret:
        return True
    if not timestamp or not signature:
        return False
    try:
        if abs(time.time() - int(timestamp)) > max_age_seconds:
            return False
    except (TypeError, ValueError):
        return False

    basestring = f"v0:{timestamp}:{body.decode()}"
    expected = "v0=" + hmac.new(
        secret.encode(), basestring.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
