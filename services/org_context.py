"""
Apply per-org credentials for the duration of a request/tool call.

Ensures org A's Slack/GitHub/Anthropic keys are never used for org B.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator, Optional

import structlog

from services.org_config import ORG_CREDENTIAL_KEYS, OrgConfig, resolve_org_credentials

log = structlog.get_logger()


@contextmanager
def org_credentials(org_id: str, org_config: Optional[OrgConfig] = None) -> Generator[dict, None, None]:
    """
    Temporarily overlay os.environ with the org's own credentials.
    Yields the merged credential dict (keys only, for logging).
    """
    org_config = org_config or OrgConfig()
    creds = resolve_org_credentials(org_id, org_config)
    previous: dict[str, Optional[str]] = {}

    for key in ORG_CREDENTIAL_KEYS:
        if key in creds:
            previous[key] = os.environ.get(key)
            os.environ[key] = str(creds[key])

    try:
        yield {k: True for k in creds}
    finally:
        for key, old in previous.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old


def refresh_agent_credentials(agent: object) -> None:
    """Re-read env-backed clients after org_credentials overlay."""
    if hasattr(agent, "client"):
        agent.client = None
    if hasattr(agent, "github_collector") and hasattr(agent.github_collector, "refresh_credentials"):
        agent.github_collector.refresh_credentials()
    if hasattr(agent, "k8s_collector") and hasattr(agent.k8s_collector, "reset"):
        agent.k8s_collector.reset()
