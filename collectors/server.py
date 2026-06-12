"""
Server Context Collector
Gathers system health metrics, service status, and logs.
"""
import asyncio
import structlog

log = structlog.get_logger()


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

    async def collect(self) -> dict:
        """Collect server health snapshot."""
        result = {}
        for key, cmd in self.SAFE_COMMANDS:
            try:
                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
                result[key] = stdout.decode().strip()
            except asyncio.TimeoutError:
                result[key] = f"timeout running: {cmd}"
            except Exception as e:
                result[key] = f"error: {e}"
        return result
