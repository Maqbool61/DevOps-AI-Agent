"""
Server Context Collector
Gathers system health metrics, service status, and logs.
"""

import asyncio
import os
from typing import Optional

import structlog

from tools.ssh_utils import build_ssh_command

log = structlog.get_logger()


def _build_ssh_args(host: str, command: str) -> list:
    """Build SSH argv for remote command execution.

    Defaults to OpenSSH's strict host-key checking (no StrictHostKeyChecking=no).
    Use SSH_KNOWN_HOSTS to point to a known_hosts file, and SSH_REMOTE_USER
    when the host is given without a user@ prefix.
    """
    ssh_args = ["ssh", "-o", "ConnectTimeout=10"]
    known_hosts = os.getenv("SSH_KNOWN_HOSTS")
    if known_hosts:
        ssh_args.extend(["-o", f"UserKnownHostsFile={known_hosts}"])
    remote_host = host
    if "@" not in remote_host:
        remote_user = os.getenv("SSH_REMOTE_USER")
        if remote_user:
            remote_host = f"{remote_user}@{remote_host}"
    ssh_args.extend([remote_host, command])
    return ssh_args


class ServerCollector:
    SAFE_COMMANDS = [
        ("disk_usage", "df -h"),
        ("memory", "free -m"),
        ("cpu_load", "uptime"),
        ("top_processes", "ps aux --sort=-%cpu | head -20"),
        ("systemd_failed", "systemctl list-units --state=failed --no-pager"),
        ("nginx_status", "systemctl status nginx --no-pager -l | tail -30"),
        ("disk_inodes", "df -i | head -10"),
        ("open_ports", "ss -tlnp | head -20"),
        ("recent_errors", "journalctl -p err -n 50 --no-pager"),
    ]

    async def collect(self, host: Optional[str] = None) -> dict:
        """Collect server health snapshot. Use host= for remote servers (centralized agent)."""
        result = {"target_host": host or "localhost"}
        commands = list(self.SAFE_COMMANDS) + [
            (
                "docker_ps_all",
                "docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}' 2>/dev/null || echo 'docker not available'",
            ),
            (
                "docker_unhealthy",
                "docker ps -a --filter 'status=restarting' --filter 'status=exited' --format '{{.Names}}: {{.Status}}' 2>/dev/null || true",
            ),
        ]
        for key, cmd in commands:
            try:
                if host and host not in ("localhost", "127.0.0.1"):
                    cmd = build_ssh_command(host, cmd)
                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
                result[key] = stdout.decode().strip() or stderr.decode().strip()
            except asyncio.TimeoutError:
                result[key] = f"timeout running: {cmd}"
            except Exception as e:
                result[key] = f"error: {e}"
        return result
