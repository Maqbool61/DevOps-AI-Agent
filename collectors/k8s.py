"""
Kubernetes Context Collector
Gathers pod logs, events, describe output, and resource metrics.
"""
import os
from typing import Optional

import structlog

log = structlog.get_logger()


class K8sCollector:
    def __init__(self):
        self._client = None
        self._apps_client = None
        self._loaded = False

    def _load(self):
        if self._loaded:
            return
        try:
            from kubernetes import client, config
            kubeconfig = os.getenv("KUBECONFIG")
            if kubeconfig:
                config.load_kube_config(kubeconfig)
            else:
                config.load_incluster_config()
            self._client = client.CoreV1Api()
            self._apps_client = client.AppsV1Api()
            self._loaded = True
            log.info("K8s client initialized (in-cluster)" if not kubeconfig else "K8s client initialized (kubeconfig)")
        except Exception as e:
            log.warning("K8s client not available", error=str(e))
            self._loaded = True  # Don't retry

    async def collect(
        self,
        namespace: str,
        pod_name: Optional[str] = None,
        include_previous: bool = True,
    ) -> dict:
        """Collect full context for a failing pod or namespace."""
        self._load()

        if not self._client:
            return {"error": "Kubernetes client not available. Check KUBECONFIG."}

        result = {}

        try:
            # Find pods
            if pod_name:
                pods = self._client.list_namespaced_pod(
                    namespace,
                    field_selector=f"metadata.name={pod_name}"
                )
                if not pods.items:
                    # Try as prefix
                    all_pods = self._client.list_namespaced_pod(namespace)
                    pods_list = [p for p in all_pods.items if p.metadata.name.startswith(pod_name)]
                else:
                    pods_list = pods.items
            else:
                all_pods = self._client.list_namespaced_pod(namespace)
                # Focus on unhealthy pods
                pods_list = [
                    p for p in all_pods.items
                    if p.status.phase in ("Failed", "Pending")
                    or any(
                        cs.state.waiting and cs.state.waiting.reason in
                        ("CrashLoopBackOff", "OOMKilled", "ImagePullBackOff", "ErrImagePull", "Error")
                        for cs in (p.status.container_statuses or [])
                    )
                ][:3]  # Max 3 pods

            result["pods"] = []
            for pod in pods_list[:3]:
                pod_info = self._describe_pod(pod, namespace, include_previous)
                result["pods"].append(pod_info)

            # Get namespace events
            events = self._client.list_namespaced_event(
                namespace,
                field_selector="type=Warning" if not pod_name else None,
            )
            result["events"] = [
                {
                    "reason": e.reason,
                    "message": e.message,
                    "object": f"{e.involved_object.kind}/{e.involved_object.name}",
                    "count": e.count,
                }
                for e in sorted(events.items, key=lambda x: x.last_timestamp or "", reverse=True)[:20]
            ]

        except Exception as e:
            log.error("K8s collection error", error=str(e))
            result["error"] = str(e)

        return result

    def _describe_pod(self, pod, namespace: str, include_previous: bool) -> dict:
        name = pod.metadata.name

        # Container states
        container_states = []
        for cs in (pod.status.container_statuses or []):
            state_info = {"name": cs.name, "ready": cs.ready, "restart_count": cs.restart_count}
            if cs.state.waiting:
                state_info["state"] = "waiting"
                state_info["reason"] = cs.state.waiting.reason
                state_info["message"] = cs.state.waiting.message
            elif cs.state.terminated:
                state_info["state"] = "terminated"
                state_info["exit_code"] = cs.state.terminated.exit_code
                state_info["reason"] = cs.state.terminated.reason
            elif cs.state.running:
                state_info["state"] = "running"
            container_states.append(state_info)

        # Resource limits
        resources = {}
        for container in (pod.spec.containers or []):
            if container.resources:
                resources[container.name] = {
                    "requests": container.resources.requests or {},
                    "limits": container.resources.limits or {},
                }

        # Fetch logs
        logs = {}
        for container in (pod.spec.containers or []):
            try:
                logs[container.name] = self._client.read_namespaced_pod_log(
                    name, namespace,
                    container=container.name,
                    tail_lines=80,
                )
            except Exception:
                pass
            if include_previous:
                try:
                    logs[f"{container.name}_previous"] = self._client.read_namespaced_pod_log(
                        name, namespace,
                        container=container.name,
                        previous=True,
                        tail_lines=80,
                    )
                except Exception:
                    pass

        return {
            "name": name,
            "phase": pod.status.phase,
            "node": pod.spec.node_name,
            "container_states": container_states,
            "resources": resources,
            "logs": logs,
            "conditions": [
                {"type": c.type, "status": c.status, "message": c.message}
                for c in (pod.status.conditions or [])
            ],
        }
