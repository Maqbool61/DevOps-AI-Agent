"""
GCP Cloud Resource Collector
Fetches diagnostic information from GCP resources (GCE, GKE, Cloud Run, Cloud Functions, etc.)
Focuses on safe read-only operations.
"""
import os
from typing import Optional

import structlog

log = structlog.get_logger()


class GCPCollector:
    def __init__(self):
        self.project_id = os.getenv("GCP_PROJECT_ID", "")
        # GCP credentials should be set via GOOGLE_APPLICATION_CREDENTIALS environment variable
        # or use service account attached to the runtime environment

    async def collect(self, resource_type: str, resource_id: str, **kwargs) -> dict:
        """
        Collect diagnostic info for GCP resources.
        
        Args:
            resource_type: 'gce', 'gke', 'cloud_run', 'cloud_function', 'cloud_sql'
            resource_id: Instance name, function name, etc.
        """
        try:
            if resource_type == "gce":
                return await self._collect_gce(resource_id, kwargs.get("zone"))
            elif resource_type == "gke":
                return await self._collect_gke_pod(kwargs.get("cluster"), kwargs.get("zone"), resource_id, kwargs.get("namespace"))
            elif resource_type == "cloud_run":
                return await self._collect_cloud_run(resource_id, kwargs.get("region"))
            elif resource_type == "cloud_function":
                return await self._collect_cloud_function(resource_id, kwargs.get("region"))
            elif resource_type == "cloud_sql":
                return await self._collect_cloud_sql(resource_id)
            else:
                return {"error": f"Unsupported GCP resource type: {resource_type}"}
        except Exception as e:
            log.error("GCP collection failed", resource_type=resource_type, error=str(e))
            return {"error": str(e)}

    async def _collect_gce(self, instance_name: str, zone: str) -> dict:
        """Collect GCE instance diagnostics."""
        try:
            from google.cloud import compute_v1
            
            client = compute_v1.InstancesClient()
            
            # Get instance details
            instance = client.get(
                project=self.project_id,
                zone=zone,
                instance=instance_name
            )
            
            # Get serial port output (useful for boot diagnostics)
            try:
                serial_output = client.get_serial_port_output(
                    project=self.project_id,
                    zone=zone,
                    instance=instance_name,
                    port=1
                )
                console_text = serial_output.contents[-4000:] if len(serial_output.contents) > 4000 else serial_output.contents
            except Exception:
                console_text = "Serial port output not available"
            
            return {
                "instance_name": instance_name,
                "zone": zone,
                "status": instance.status,
                "machine_type": instance.machine_type.split("/")[-1],
                "creation_timestamp": instance.creation_timestamp,
                "network_interfaces": [
                    {
                        "network": ni.network.split("/")[-1],
                        "internal_ip": ni.network_i_p,
                        "external_ip": ni.access_configs[0].nat_i_p if ni.access_configs else None,
                    }
                    for ni in instance.network_interfaces
                ],
                "labels": dict(instance.labels) if instance.labels else {},
                "console_output": console_text,
            }
        except ImportError:
            return {"error": "google-cloud-compute not installed. Run: pip install google-cloud-compute"}
        except Exception as e:
            return {"error": f"GCE collection failed: {str(e)}"}

    async def _collect_gke_pod(self, cluster: str, zone: str, pod_name: str, namespace: str = "default") -> dict:
        """Collect GKE pod diagnostics (delegates to K8s collector but includes GKE context)."""
        try:
            from google.cloud import container_v1
            
            client = container_v1.ClusterManagerClient()
            
            # Get cluster info
            cluster_path = f"projects/{self.project_id}/locations/{zone}/clusters/{cluster}"
            cluster_info = client.get_cluster(name=cluster_path)
            
            # For actual pod logs, this would delegate to the K8sCollector
            # Here we just return cluster context
            return {
                "cluster": cluster,
                "zone": zone,
                "cluster_status": cluster_info.status.name,
                "cluster_version": cluster_info.current_master_version,
                "node_pools": len(cluster_info.node_pools),
                "endpoint": cluster_info.endpoint,
                "note": "Use K8s collector for detailed pod logs",
                "pod_name": pod_name,
                "namespace": namespace,
            }
        except ImportError:
            return {"error": "google-cloud-container not installed. Run: pip install google-cloud-container"}
        except Exception as e:
            return {"error": f"GKE collection failed: {str(e)}"}

    async def _collect_cloud_run(self, service_name: str, region: str) -> dict:
        """Collect Cloud Run service diagnostics."""
        try:
            from google.cloud import run_v2
            from google.cloud import logging as cloud_logging
            
            client = run_v2.ServicesClient()
            
            # Get service details
            service_path = f"projects/{self.project_id}/locations/{region}/services/{service_name}"
            service = client.get_service(name=service_path)
            
            # Get recent logs
            logging_client = cloud_logging.Client(project=self.project_id)
            
            filter_str = f'resource.type="cloud_run_revision" AND resource.labels.service_name="{service_name}" AND severity>=ERROR'
            
            recent_errors = []
            try:
                entries = logging_client.list_entries(filter_=filter_str, page_size=20)
                for entry in entries:
                    recent_errors.append({
                        "timestamp": str(entry.timestamp),
                        "severity": entry.severity,
                        "message": entry.payload[:500] if isinstance(entry.payload, str) else str(entry.payload)[:500],
                    })
            except Exception:
                recent_errors = [{"error": "Unable to fetch logs"}]
            
            return {
                "service_name": service_name,
                "region": region,
                "uri": service.uri,
                "latest_ready_revision": service.latest_ready_revision,
                "latest_created_revision": service.latest_created_revision,
                "ingress": service.ingress.name if service.ingress else None,
                "labels": dict(service.labels) if service.labels else {},
                "recent_errors": recent_errors[:10],
            }
        except ImportError:
            return {"error": "google-cloud-run or google-cloud-logging not installed"}
        except Exception as e:
            return {"error": f"Cloud Run collection failed: {str(e)}"}

    async def _collect_cloud_function(self, function_name: str, region: str) -> dict:
        """Collect Cloud Function diagnostics."""
        try:
            from google.cloud import functions_v2
            from google.cloud import logging as cloud_logging
            
            client = functions_v2.FunctionServiceClient()
            
            # Get function details
            function_path = f"projects/{self.project_id}/locations/{region}/functions/{function_name}"
            function = client.get_function(name=function_path)
            
            # Get recent logs
            logging_client = cloud_logging.Client(project=self.project_id)
            
            filter_str = f'resource.type="cloud_function" AND resource.labels.function_name="{function_name}" AND severity>=ERROR'
            
            recent_errors = []
            try:
                entries = logging_client.list_entries(filter_=filter_str, page_size=20)
                for entry in entries:
                    recent_errors.append({
                        "timestamp": str(entry.timestamp),
                        "severity": entry.severity,
                        "message": entry.payload[:500] if isinstance(entry.payload, str) else str(entry.payload)[:500],
                    })
            except Exception:
                recent_errors = [{"error": "Unable to fetch logs"}]
            
            return {
                "function_name": function_name,
                "region": region,
                "state": function.state.name,
                "runtime": function.build_config.runtime,
                "entry_point": function.build_config.entry_point,
                "url": function.service_config.uri if hasattr(function.service_config, 'uri') else None,
                "labels": dict(function.labels) if function.labels else {},
                "recent_errors": recent_errors[:10],
            }
        except ImportError:
            return {"error": "google-cloud-functions or google-cloud-logging not installed"}
        except Exception as e:
            return {"error": f"Cloud Function collection failed: {str(e)}"}

    async def _collect_cloud_sql(self, instance_name: str) -> dict:
        """Collect Cloud SQL instance diagnostics."""
        try:
            from google.cloud.sql_v1 import SqlInstancesServiceClient
            
            client = SqlInstancesServiceClient()
            
            # Get instance details
            instance = client.get(
                project=self.project_id,
                instance=instance_name
            )
            
            return {
                "instance_name": instance_name,
                "state": instance.state.name,
                "database_version": instance.database_version.name,
                "region": instance.region,
                "tier": instance.settings.tier,
                "availability_type": instance.settings.availability_type.name,
                "backup_enabled": instance.settings.backup_configuration.enabled if instance.settings.backup_configuration else False,
                "ip_addresses": [
                    {
                        "type": ip.type_.name,
                        "address": ip.ip_address,
                    }
                    for ip in instance.ip_addresses
                ],
            }
        except ImportError:
            return {"error": "google-cloud-sql not installed. Run: pip install google-cloud-sql"}
        except Exception as e:
            return {"error": f"Cloud SQL collection failed: {str(e)}"}
