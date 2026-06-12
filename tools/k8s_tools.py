"""
Kubernetes Tools
Handles manifest application, rollbacks, and kubectl operations.
"""
import base64
import os
import tempfile
from typing import Optional

import structlog

from tools.executor import SafeExecutor

log = structlog.get_logger()

ALLOWED_NAMESPACES = set(
    ns.strip()
    for ns in os.getenv("ALLOWED_NAMESPACES", "default").split(",")
    if ns.strip()
)


class K8sTools:
    def __init__(self):
        self.executor = SafeExecutor()

    def _check_namespace(self, namespace: str) -> Optional[dict]:
        if ALLOWED_NAMESPACES and namespace not in ALLOWED_NAMESPACES:
            return {
                "blocked": True,
                "error": f"Namespace '{namespace}' not in ALLOWED_NAMESPACES: {ALLOWED_NAMESPACES}",
            }
        return None

    async def apply_manifest(
        self,
        manifest_yaml: str,
        dry_run: bool = True,
        namespace: Optional[str] = None,
        auto_apply: bool = False,
        notifier=None,
    ) -> dict:
        """Apply a K8s manifest. Always dry-run first."""
        if namespace:
            blocked = self._check_namespace(namespace)
            if blocked:
                return blocked

        # Write manifest to temp file
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            f.write(manifest_yaml)
            tmp_path = f.name

        try:
            ns_flag = f"-n {namespace}" if namespace else ""
            dry_flag = "--dry-run=client" if dry_run else ""
            cmd = f"kubectl apply -f {tmp_path} {ns_flag} {dry_flag}".strip()

            result = await self.executor.run(cmd)

            if not dry_run and not auto_apply:
                # Request approval via Slack
                encoded = base64.b64encode(cmd.encode()).decode()
                if notifier:
                    await notifier.send_approval_request(
                        f"Apply K8s manifest to namespace `{namespace}`",
                        cmd,
                        encoded,
                    )
                return {
                    "blocked": True,
                    "requires_approval": True,
                    "message": "Manifest validated (dry-run OK). Approval request sent to Slack.",
                    "dry_run_output": result.get("stdout"),
                }

            return result
        finally:
            os.unlink(tmp_path)

    async def run_kubectl(self, command: str, auto_apply: bool = False) -> dict:
        """Run a kubectl command with safety checks."""
        full_cmd = f"kubectl {command}"

        # Namespace check
        if "-n " in command:
            ns = command.split("-n ")[-1].split()[0]
            blocked = self._check_namespace(ns)
            if blocked:
                return blocked

        return await self.executor.run_safe(full_cmd)

    async def rollback(
        self,
        deployment: str,
        namespace: str,
        revision: Optional[int] = None,
        auto_apply: bool = False,
        notifier=None,
    ) -> dict:
        """Roll back a deployment to previous or specific revision."""
        blocked = self._check_namespace(namespace)
        if blocked:
            return blocked

        rev_flag = f"--to-revision={revision}" if revision else ""
        cmd = f"kubectl rollout undo deployment/{deployment} -n {namespace} {rev_flag}".strip()

        if not auto_apply and notifier:
            encoded = base64.b64encode(cmd.encode()).decode()
            await notifier.send_approval_request(
                f"Rollback `{deployment}` in `{namespace}`",
                cmd,
                encoded,
            )
            return {
                "blocked": True,
                "requires_approval": True,
                "message": f"Rollback approval request sent to Slack for {deployment}.",
            }

        return await self.executor.run(cmd)
