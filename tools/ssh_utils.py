"""
SSH command helpers — strict host key checking by default.
"""
import os
import shlex


def _strict_host_key_checking() -> bool:
    return os.getenv("SSH_STRICT_HOST_KEY_CHECKING", "true").lower() != "false"


def format_ssh_target(host: str) -> str:
    """Apply SSH_REMOTE_USER when host has no user@ prefix."""
    host = host.strip()
    remote_user = os.getenv("SSH_REMOTE_USER", "").strip()
    if remote_user and "@" not in host:
        return f"{remote_user}@{host}"
    return host


def build_ssh_command(host: str, remote_command: str) -> str:
    """Build an ssh invocation with safe defaults."""
    target = format_ssh_target(host)
    opts = ["-o", f"ConnectTimeout={os.getenv('SSH_CONNECT_TIMEOUT', '10')}"]

    if _strict_host_key_checking():
        known_hosts = os.getenv("SSH_KNOWN_HOSTS", "").strip()
        if known_hosts:
            opts.extend(["-o", f"UserKnownHostsFile={known_hosts}"])
        opts.extend(["-o", "StrictHostKeyChecking=yes"])
    else:
        opts.extend(["-o", "StrictHostKeyChecking=no"])

    opt_str = " ".join(shlex.quote(o) for o in opts)
    escaped_cmd = remote_command.replace("'", "'\"'\"'")
    return f"ssh {opt_str} {shlex.quote(target)} '{escaped_cmd}'"
