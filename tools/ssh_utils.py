"""
SSH command helpers — strict host key checking by default.
"""
import os
import shlex
from typing import List


def _strict_host_key_checking() -> bool:
    return os.getenv("SSH_STRICT_HOST_KEY_CHECKING", "true").lower() != "false"


def format_ssh_target(host: str) -> str:
    """Apply SSH_REMOTE_USER when host has no user@ prefix."""
    host = host.strip()
    remote_user = os.getenv("SSH_REMOTE_USER", "").strip()
    if remote_user and "@" not in host:
        return f"{remote_user}@{host}"
    return host


def build_ssh_argv(host: str, remote_command: str) -> List[str]:
    """Build SSH argv for remote command execution (no shell on local side)."""
    target = format_ssh_target(host)
    argv = [
        "ssh",
        "-o",
        f"ConnectTimeout={os.getenv('SSH_CONNECT_TIMEOUT', '10')}",
    ]

    if _strict_host_key_checking():
        known_hosts = os.getenv("SSH_KNOWN_HOSTS", "").strip()
        if known_hosts:
            argv.extend(["-o", f"UserKnownHostsFile={known_hosts}"])
        argv.extend(["-o", "StrictHostKeyChecking=yes"])
    else:
        argv.extend(["-o", "StrictHostKeyChecking=no"])

    argv.extend([target, remote_command])
    return argv


def build_ssh_command(host: str, remote_command: str) -> str:
    """Human-readable SSH command string (for logs and display)."""
    return " ".join(shlex.quote(part) for part in build_ssh_argv(host, remote_command))
