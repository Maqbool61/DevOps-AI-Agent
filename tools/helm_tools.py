"""
Helm Tools — safe Helm operations (no uninstall/delete).
"""
import base64
import os
import re
from typing import Optional

import structlog

from collectors.helm import HelmCollector
from tools.executor import SafeExecutor

log = structlog.get_logger()

ALLOWED_NAMESPACES = set(
    ns.strip()
    for ns in os.getenv("ALLOWED_NAMESPACES", "default").split(",")
    if ns.strip()
)

BLOCKED_HELM_PATTERNS = [
    r"\buninstall\b",
    r"\bdelete\b",
    r"\bpurge\b",
]

SAFE_HELM_PREFIXES = [
    "helm status",
    "helm history",
    "helm get values",
    "helm get manifest",
    "helm list",
    "helm rollback",
    "helm upgrade",
]


class HelmTools:
    def __init__(self):
        self.collector = HelmCollector()
        self.executor = SafeExecutor()
        self.helm_bin = os.getenv("HELM_BIN", "helm")

    def _check_namespace(self, namespace: str) -> Optional[dict]:
        if ALLOWED_NAMESPACES and namespace not in ALLOWED_NAMESPACES:
            return {
                "blocked": True,
                "error": f"Namespace '{namespace}' not in ALLOWED_NAMESPACES: {ALLOWED_NAMESPACES}",
            }
        return None

    def _is_blocked(self, command: str) -> Optional[str]:
        cmd = command.lower()
        for pattern in BLOCKED_HELM_PATTERNS:
            if re.search(pattern, cmd):
                return f"Blocked Helm operation: {pattern}"
        return None

    async def get_release(self, release_name: str, namespace: str = "default") -> dict:
        blocked = self._check_namespace(namespace)
        if blocked:
            return blocked
        return await self.collector.collect(release_name, namespace)

    async def rollback(
        self,
        release_name: str,
        namespace: str,
        revision: Optional[int] = None,
        auto_apply: bool = False,
        notifier=None,
    ) -> dict:
        blocked = self._check_namespace(namespace)
        if blocked:
            return blocked

        rev_part = str(revision) if revision is not None else ""
        cmd = f"{self.helm_bin} rollback {release_name} {rev_part} -n {namespace}".strip()

        block_reason = self._is_blocked(cmd)
        if block_reason:
            return {"blocked": True, "error": block_reason}

        if not auto_apply:
            if notifier:
                await notifier.send_approval_request(
                    f"Helm rollback `{release_name}` in `{namespace}`",
                    cmd,
                    base64.b64encode(cmd.encode()).decode(),
                )
            return {
                "blocked": True,
                "requires_approval": True,
                "message": "Helm rollback requires approval (AUTO_APPLY=false)",
                "command": cmd,
            }

        return await self.executor.run(cmd)

    async def upgrade(
        self,
        release_name: str,
        chart: str,
        namespace: str,
        values_yaml: Optional[str] = None,
        dry_run: bool = True,
        auto_apply: bool = False,
        notifier=None,
    ) -> dict:
        blocked = self._check_namespace(namespace)
        if blocked:
            return blocked

        dry_flag = "--dry-run" if dry_run else ""
        values_flag = ""
        tmp_path = None
        if values_yaml:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
                f.write(values_yaml)
                tmp_path = f.name
            values_flag = f"-f {tmp_path}"

        cmd = (
            f"{self.helm_bin} upgrade {release_name} {chart} -n {namespace} "
            f"{values_flag} {dry_flag} --install"
        ).strip()

        try:
            block_reason = self._is_blocked(cmd)
            if block_reason:
                return {"blocked": True, "error": block_reason}

            if dry_run:
                return await self.executor.run(cmd)

            if not auto_apply:
                if notifier:
                    await notifier.send_approval_request(
                        f"Helm upgrade `{release_name}` in `{namespace}`",
                        cmd,
                        base64.b64encode(cmd.encode()).decode(),
                    )
                return {
                    "blocked": True,
                    "requires_approval": True,
                    "message": "Helm upgrade requires approval (AUTO_APPLY=false)",
                    "command": cmd,
                }

            return await self.executor.run(cmd)
        finally:
            if tmp_path:
                os.unlink(tmp_path)
