"""
Safe Command Executor
Enforces command whitelists and human approval gates before running anything.
"""

import asyncio
import base64
import os
from typing import Optional

import structlog

log = structlog.get_logger()


def _build_ssh_args(host: str, command: str) -> list:
    """Build SSH argv for remote command execution.

    Defaults to OpenSSH's strict host-key checking (no StrictHostKeyChecking=no).
    Use SSH_KNOWN_HOSTS to point to a known_hosts file, and SSH_REMOTE_USER
    when the host is given without a user@ prefix.
    """
    ssh_args = ["ssh"]
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


# Commands that can always auto-run (read-only or safe restarts)
ALWAYS_SAFE = [
    "kubectl get",
    "kubectl describe",
    "kubectl logs",
    "kubectl rollout status",
    "kubectl rollout history",
    "kubectl top",
    "kubectl version",
    "df ",
    "df -",
    "free ",
    "uptime",
    "ps aux",
    "ss -",
    "journalctl",
    "systemctl status",
    "systemctl is-active",
    "nginx -t",
    "docker ps",
    "docker images",
    "docker logs",
    "docker inspect",
    "docker stats",
]

# Commands allowed when AUTO_APPLY=true
ALLOWED_WITH_AUTO_APPLY = [
    "kubectl rollout restart",
    "kubectl scale",
    "kubectl apply",
    "kubectl rollout undo",
    "systemctl restart",
    "systemctl reload",
    "nginx -s reload",
    "nginx -s reopen",
    "docker restart",
    "docker start",
    "docker stop",
]

# Commands that ALWAYS need human approval
ALWAYS_REQUIRE_APPROVAL = [
    "kubectl delete",
    "kubectl exec",
    "rm ",
    "rm -",
    "dd ",
    "mkfs",
    "fdisk",
    "kill -9",
    "shutdown",
    "reboot",
]


class SafeExecutor:
    def __init__(self):
        self.auto_apply = os.getenv("AUTO_APPLY", "false").lower() == "true"

    def _classify(self, command: str) -> str:
        """Returns 'safe', 'allowed', 'requires_approval', or 'blocked'."""
        cmd = command.strip().lower()

        for blocked in ALWAYS_REQUIRE_APPROVAL:
            if blocked in cmd:
                return "requires_approval"

        for safe in ALWAYS_SAFE:
            if cmd.startswith(safe.lower()) or safe.lower() in cmd:
                return "safe"

        for allowed in ALLOWED_WITH_AUTO_APPLY:
            if cmd.startswith(allowed.lower()):
                return "allowed"

        return "requires_approval"

    async def run(self, command: str, host: Optional[str] = None) -> dict:
        """Run a command, bypassing safety for internal approved calls."""
        return await self._exec(command, host)

    async def run_safe(self, command: str, host: Optional[str] = None) -> dict:
        """Run with full safety checks."""
        classification = self._classify(command)

        if classification == "requires_approval":
            if not self.auto_apply:
                encoded = base64.b64encode(command.encode()).decode()
                return {
                    "blocked": True,
                    "requires_approval": True,
                    "command": command,
                    "approval_payload": encoded,
                    "message": f"Command requires human approval: `{command}`",
                }

        if classification == "allowed" and not self.auto_apply:
            encoded = base64.b64encode(command.encode()).decode()
            return {
                "blocked": True,
                "requires_approval": True,
                "command": command,
                "approval_payload": encoded,
                "message": f"AUTO_APPLY=false. Approval needed for: `{command}`",
            }

        return await self._exec(command, host)

    async def _exec(self, command: str, host: Optional[str] = None) -> dict:
        """Execute the command."""
        if host and host not in ("localhost", "127.0.0.1", ""):
            # SSH to remote host
            ssh_args = _build_ssh_args(host, command)
            display_command = " ".join(ssh_args)
            log.info("Executing command", command=display_command)

            try:
                proc = await asyncio.create_subprocess_exec(
                    *ssh_args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
                return {
                    "success": proc.returncode == 0,
                    "returncode": proc.returncode,
                    "stdout": stdout.decode().strip()[-3000:],  # Truncate
                    "stderr": stderr.decode().strip()[-1000:],
                    "command": display_command,
                }
            except asyncio.TimeoutError:
                return {
                    "success": False,
                    "error": "Command timed out after 60s",
                    "command": display_command,
                }
            except Exception as e:
                return {"success": False, "error": str(e), "command": display_command}

        log.info("Executing command", command=command)

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            return {
                "success": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": stdout.decode().strip()[-3000:],  # Truncate
                "stderr": stderr.decode().strip()[-1000:],
                "command": command,
            }
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Command timed out after 60s",
                "command": command,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "command": command}
