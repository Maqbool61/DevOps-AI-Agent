"""
Azure Cloud Resource Collector
Fetches diagnostic information from Azure resources (VMs, AKS, App Service, Functions, etc.)
Focuses on safe read-only operations.
"""
import os
from typing import Optional

import structlog

log = structlog.get_logger()


class AzureCollector:
    def __init__(self):
        self.subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID", "")
        # Azure credentials should be set via environment variables:
        # AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET
        # or use managed identity

    async def collect(self, resource_type: str, resource_name: str, **kwargs) -> dict:
        """
        Collect diagnostic info for Azure resources.
        
        Args:
            resource_type: 'vm', 'aks', 'app_service', 'function', 'sql'
            resource_name: Resource name
        """
        try:
            if resource_type == "vm":
                return await self._collect_vm(resource_name, kwargs.get("resource_group"))
            elif resource_type == "aks":
                return await self._collect_aks(resource_name, kwargs.get("resource_group"))
            elif resource_type == "app_service":
                return await self._collect_app_service(resource_name, kwargs.get("resource_group"))
            elif resource_type == "function":
                return await self._collect_function(resource_name, kwargs.get("resource_group"))
            elif resource_type == "sql":
                return await self._collect_sql(resource_name, kwargs.get("resource_group"))
            else:
                return {"error": f"Unsupported Azure resource type: {resource_type}"}
        except Exception as e:
            log.error("Azure collection failed", resource_type=resource_type, error=str(e))
            return {"error": str(e)}

    async def _collect_vm(self, vm_name: str, resource_group: str) -> dict:
        """Collect Azure VM diagnostics."""
        try:
            from azure.identity import DefaultAzureCredential
            from azure.mgmt.compute import ComputeManagementClient
            from azure.mgmt.monitor import MonitorManagementClient
            from datetime import datetime, timedelta
            
            credential = DefaultAzureCredential()
            compute_client = ComputeManagementClient(credential, self.subscription_id)
            monitor_client = MonitorManagementClient(credential, self.subscription_id)
            
            # Get VM details
            vm = compute_client.virtual_machines.get(
                resource_group_name=resource_group,
                vm_name=vm_name,
                expand="instanceView"
            )
            
            # Get VM instance view for status
            instance_view = vm.instance_view
            
            # Get recent activity logs (last hour)
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=1)
            
            filter_str = f"eventTimestamp ge '{start_time.isoformat()}' and resourceUri eq '{vm.id}'"
            
            activity_logs = []
            try:
                logs = monitor_client.activity_logs.list(filter=filter_str)
                for log_entry in logs:
                    if log_entry.level in ["Error", "Critical", "Warning"]:
                        activity_logs.append({
                            "timestamp": str(log_entry.event_timestamp),
                            "level": log_entry.level,
                            "operation": log_entry.operation_name.localized_value,
                            "status": log_entry.status.localized_value,
                        })
            except Exception:
                activity_logs = [{"error": "Unable to fetch activity logs"}]
            
            return {
                "vm_name": vm_name,
                "resource_group": resource_group,
                "location": vm.location,
                "vm_size": vm.hardware_profile.vm_size,
                "os_type": vm.storage_profile.os_disk.os_type,
                "provisioning_state": vm.provisioning_state,
                "power_state": instance_view.statuses[-1].code if instance_view and instance_view.statuses else "Unknown",
                "vm_agent_status": instance_view.vm_agent.statuses[0].display_status if instance_view and instance_view.vm_agent else "Unknown",
                "disks": [
                    {
                        "name": disk.name,
                        "size_gb": disk.disk_size_gb,
                        "caching": disk.caching,
                    }
                    for disk in ([vm.storage_profile.os_disk] + list(vm.storage_profile.data_disks))
                ],
                "recent_activity": activity_logs[:10],
                "tags": vm.tags or {},
            }
        except ImportError:
            return {"error": "azure-mgmt-compute and azure-identity not installed. Run: pip install azure-mgmt-compute azure-identity azure-mgmt-monitor"}
        except Exception as e:
            return {"error": f"Azure VM collection failed: {str(e)}"}

    async def _collect_aks(self, cluster_name: str, resource_group: str) -> dict:
        """Collect AKS cluster diagnostics."""
        try:
            from azure.identity import DefaultAzureCredential
            from azure.mgmt.containerservice import ContainerServiceClient
            
            credential = DefaultAzureCredential()
            aks_client = ContainerServiceClient(credential, self.subscription_id)
            
            # Get cluster details
            cluster = aks_client.managed_clusters.get(
                resource_group_name=resource_group,
                resource_name=cluster_name
            )
            
            # Get node pools
            node_pools = list(aks_client.agent_pools.list(
                resource_group_name=resource_group,
                resource_name=cluster_name
            ))
            
            return {
                "cluster_name": cluster_name,
                "resource_group": resource_group,
                "location": cluster.location,
                "kubernetes_version": cluster.kubernetes_version,
                "provisioning_state": cluster.provisioning_state,
                "power_state": cluster.power_state.code if cluster.power_state else "Unknown",
                "fqdn": cluster.fqdn,
                "node_pools": [
                    {
                        "name": pool.name,
                        "count": pool.count,
                        "vm_size": pool.vm_size,
                        "os_type": pool.os_type,
                        "provisioning_state": pool.provisioning_state,
                    }
                    for pool in node_pools
                ],
                "network_profile": {
                    "network_plugin": cluster.network_profile.network_plugin if cluster.network_profile else None,
                    "service_cidr": cluster.network_profile.service_cidr if cluster.network_profile else None,
                },
                "tags": cluster.tags or {},
                "note": "Use K8s collector for detailed pod logs",
            }
        except ImportError:
            return {"error": "azure-mgmt-containerservice not installed. Run: pip install azure-mgmt-containerservice azure-identity"}
        except Exception as e:
            return {"error": f"AKS collection failed: {str(e)}"}

    async def _collect_app_service(self, app_name: str, resource_group: str) -> dict:
        """Collect Azure App Service diagnostics."""
        try:
            from azure.identity import DefaultAzureCredential
            from azure.mgmt.web import WebSiteManagementClient
            import httpx
            
            credential = DefaultAzureCredential()
            web_client = WebSiteManagementClient(credential, self.subscription_id)
            
            # Get app details
            app = web_client.web_apps.get(
                resource_group_name=resource_group,
                name=app_name
            )
            
            # Get app logs (recent entries from default logs)
            # Note: This requires Kudu API access
            logs_summary = "Use Azure Portal or Kudu API for detailed logs"
            
            try:
                # Get publishing credentials
                creds = web_client.web_apps.list_publishing_credentials(
                    resource_group_name=resource_group,
                    name=app_name
                ).result()
                
                # Try to get recent logs via Kudu API
                kudu_url = f"https://{app_name}.scm.azurewebsites.net/api/logs/recent"
                async with httpx.AsyncClient(
                    auth=(creds.publishing_user_name, creds.publishing_password),
                    timeout=30
                ) as client:
                    logs_resp = await client.get(kudu_url)
                    if logs_resp.status_code == 200:
                        logs_data = logs_resp.json()
                        logs_summary = "\n".join([entry.get("message", "") for entry in logs_data[:20]])
            except Exception:
                pass
            
            return {
                "app_name": app_name,
                "resource_group": resource_group,
                "location": app.location,
                "state": app.state,
                "enabled": app.enabled,
                "default_host_name": app.default_host_name,
                "repository_site_name": app.repository_site_name,
                "runtime_stack": app.site_config.linux_fx_version if app.site_config else "Unknown",
                "https_only": app.https_only,
                "recent_logs": logs_summary,
                "tags": app.tags or {},
            }
        except ImportError:
            return {"error": "azure-mgmt-web not installed. Run: pip install azure-mgmt-web azure-identity"}
        except Exception as e:
            return {"error": f"App Service collection failed: {str(e)}"}

    async def _collect_function(self, function_app_name: str, resource_group: str) -> dict:
        """Collect Azure Function App diagnostics."""
        try:
            from azure.identity import DefaultAzureCredential
            from azure.mgmt.web import WebSiteManagementClient
            
            credential = DefaultAzureCredential()
            web_client = WebSiteManagementClient(credential, self.subscription_id)
            
            # Function Apps are a type of Web App
            func_app = web_client.web_apps.get(
                resource_group_name=resource_group,
                name=function_app_name
            )
            
            # Get function list
            functions = list(web_client.web_apps.list_functions(
                resource_group_name=resource_group,
                name=function_app_name
            ))
            
            return {
                "function_app_name": function_app_name,
                "resource_group": resource_group,
                "location": func_app.location,
                "state": func_app.state,
                "enabled": func_app.enabled,
                "default_host_name": func_app.default_host_name,
                "runtime": func_app.site_config.linux_fx_version or func_app.site_config.windows_fx_version if func_app.site_config else "Unknown",
                "functions": [
                    {
                        "name": f.name,
                        "function_app_id": f.function_app_id,
                    }
                    for f in functions[:20]
                ],
                "tags": func_app.tags or {},
                "note": "Check Application Insights for detailed function logs",
            }
        except ImportError:
            return {"error": "azure-mgmt-web not installed. Run: pip install azure-mgmt-web azure-identity"}
        except Exception as e:
            return {"error": f"Function App collection failed: {str(e)}"}

    async def _collect_sql(self, server_name: str, resource_group: str, database_name: Optional[str] = None) -> dict:
        """Collect Azure SQL diagnostics."""
        try:
            from azure.identity import DefaultAzureCredential
            from azure.mgmt.sql import SqlManagementClient
            
            credential = DefaultAzureCredential()
            sql_client = SqlManagementClient(credential, self.subscription_id)
            
            # Get server details
            server = sql_client.servers.get(
                resource_group_name=resource_group,
                server_name=server_name
            )
            
            # Get databases
            databases = list(sql_client.databases.list_by_server(
                resource_group_name=resource_group,
                server_name=server_name
            ))
            
            result = {
                "server_name": server_name,
                "resource_group": resource_group,
                "location": server.location,
                "state": server.state,
                "version": server.version,
                "fully_qualified_domain_name": server.fully_qualified_domain_name,
                "databases": [
                    {
                        "name": db.name,
                        "status": db.status,
                        "sku": db.sku.name if db.sku else "Unknown",
                    }
                    for db in databases if db.name != "master"
                ][:10],
                "tags": server.tags or {},
            }
            
            # If specific database requested, get more details
            if database_name:
                db = sql_client.databases.get(
                    resource_group_name=resource_group,
                    server_name=server_name,
                    database_name=database_name
                )
                result["database_details"] = {
                    "name": db.name,
                    "status": db.status,
                    "sku": db.sku.name if db.sku else "Unknown",
                    "max_size_bytes": db.max_size_bytes,
                    "creation_date": str(db.creation_date) if db.creation_date else None,
                }
            
            return result
        except ImportError:
            return {"error": "azure-mgmt-sql not installed. Run: pip install azure-mgmt-sql azure-identity"}
        except Exception as e:
            return {"error": f"Azure SQL collection failed: {str(e)}"}
