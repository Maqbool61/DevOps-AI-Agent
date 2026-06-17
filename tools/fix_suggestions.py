"""
Non-destructive fix suggestions — Claude proposes fixes without executing them.
Validated against destructive command patterns before recording.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# Patterns that must never appear in suggested commands
DESTRUCTIVE_PATTERNS = [
    r"\bdelete\b",
    r"\bdestroy\b",
    r"\bterminate\b",
    r"\bdrop\b",
    r"\btruncate\b",
    r"\brm\s+-[rf]",
    r"\brm\s+-",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"\bformat\b",
    r"\bwipe\b",
    r"\bpurge\b",
    r"\bkill\s+-9\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"kubectl\s+delete",
    r"--force-delete",
    r"DROP\s+DATABASE",
    r"DROP\s+TABLE",
]

# Explicitly allowed non-destructive fix categories (informational)
SAFE_FIX_EXAMPLES = [
    "systemctl restart/reload",
    "docker restart/start",
    "kubectl rollout restart",
    "kubectl apply (config changes)",
    "nginx -s reload",
    "scale up replicas",
    "add missing environment variables",
    "update ConfigMap/compose YAML",
    "retry pipeline",
    "open PR with config fix",
]


def is_non_destructive(command: str) -> Tuple[bool, Optional[str]]:
    """Return (ok, rejection_reason)."""
    cmd_lower = command.strip().lower()
    if not cmd_lower:
        return False, "Empty command"
    for pattern in DESTRUCTIVE_PATTERNS:
        if re.search(pattern, cmd_lower, re.IGNORECASE):
            return False, f"Destructive pattern blocked: {pattern}"
    return True, None


def validate_suggestion(
    title: str,
    description: str,
    commands: List[str],
    config_snippets: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Validate and build a suggestion record."""
    blocked = []
    approved_commands = []

    for cmd in commands:
        ok, reason = is_non_destructive(cmd)
        if ok:
            approved_commands.append(cmd)
        else:
            blocked.append({"command": cmd, "reason": reason})

    if not approved_commands and not (config_snippets or []):
        return {
            "recorded": False,
            "error": "No non-destructive commands or config snippets provided",
            "blocked_commands": blocked,
        }

    return {
        "recorded": True,
        "title": title,
        "description": description,
        "commands": approved_commands,
        "config_snippets": config_snippets or [],
        "blocked_commands": blocked,
        "non_destructive": True,
        "apply_note": (
            "These are suggestions only — not executed automatically unless "
            "AUTO_APPLY=true and command is in the safe executor whitelist."
        ),
    }
