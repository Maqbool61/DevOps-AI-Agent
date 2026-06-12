"""
DevOps AI Agent — Core Agent Loop
Uses Claude's tool_use to reason, decide, and act on infrastructure incidents.
"""
import json
import os
from typing import Any

import anthropic
import structlog

from agent.classifier import classify_issue, get_cicd_platform
from agent.prompts import get_system_prompt
from collectors.k8s import K8sCollector
from collectors.github import GitHubCollector
from collectors.gitlab import GitLabCollector
from collectors.jenkins import JenkinsCollector
from collectors.bamboo import BambooCollector
from collectors.azure_devops import AzureDevOpsCollector
from collectors.argocd import ArgoCDCollector
from collectors.aws import AWSCollector
from collectors.gcp import GCPCollector
from collectors.azure import AzureCollector
from collectors.server import ServerCollector
from tools.executor import SafeExecutor
from tools.k8s_tools import K8sTools
from tools.github_tools import GitHubTools
from tools.cicd_tools import CICDTools
from tools.argocd_tools import ArgoCDTools
from tools.cloud_tools import CloudTools
from tools.notify import SlackNotifier
from collectors.database_policy import check_database_access

log = structlog.get_logger()

AGENT_TOOLS = [
    {
        "name": "get_k8s_context",
        "description": "Fetch Kubernetes pod logs, events, describe output, and resource usage for a failing pod.",
        "input_schema": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "K8s namespace"},
                "pod_name": {"type": "string", "description": "Pod name or prefix"},
                "include_previous": {"type": "boolean", "description": "Include logs from previous crashed container"},
            },
            "required": ["namespace"],
        },
    },
    {
        "name": "get_github_logs",
        "description": "Fetch the full failed job logs from a GitHub Actions workflow run.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "owner/repo"},
                "run_id": {"type": "integer", "description": "Workflow run ID"},
            },
            "required": ["repo", "run_id"],
        },
    },
    {
        "name": "apply_k8s_manifest",
        "description": "Apply a fixed Kubernetes YAML manifest. Always dry_run=true first.",
        "input_schema": {
            "type": "object",
            "properties": {
                "manifest_yaml": {"type": "string", "description": "Complete YAML manifest"},
                "dry_run": {"type": "boolean", "description": "If true, validate only (don't apply). Default true."},
                "namespace": {"type": "string"},
            },
            "required": ["manifest_yaml"],
        },
    },
    {
        "name": "run_kubectl",
        "description": "Run a safe kubectl command (restart, scale, rollout). No delete commands.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "kubectl command without 'kubectl' prefix, e.g. 'rollout restart deployment/api -n production'"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "run_shell_command",
        "description": "Run a safe server remediation command (systemctl, nginx, df, ps). No rm or destructive commands.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "host": {"type": "string", "description": "Target host (optional, defaults to localhost)"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "create_github_pr",
        "description": "Create a GitHub PR with a config/Dockerfile fix applied to a branch.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string"},
                "file_path": {"type": "string", "description": "File to update e.g. '.github/workflows/deploy.yml'"},
                "new_content": {"type": "string", "description": "Full new file content"},
                "pr_title": {"type": "string"},
                "pr_body": {"type": "string"},
            },
            "required": ["repo", "file_path", "new_content", "pr_title", "pr_body"],
        },
    },
    {
        "name": "rollback_deployment",
        "description": "Roll back a Kubernetes deployment to the previous revision.",
        "input_schema": {
            "type": "object",
            "properties": {
                "deployment": {"type": "string"},
                "namespace": {"type": "string"},
                "revision": {"type": "integer", "description": "Specific revision number, or omit for previous"},
            },
            "required": ["deployment", "namespace"],
        },
    },
    {
        "name": "notify_slack",
        "description": "Send a message to Slack with diagnosis and actions taken.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Human-readable summary"},
                "severity": {"type": "string", "enum": ["info", "warning", "critical"]},
                "resolved": {"type": "boolean"},
                "requires_approval": {"type": "boolean"},
                "approval_command": {"type": "string", "description": "Command that needs human approval"},
            },
            "required": ["message", "severity"],
        },
    },
    # ─── Multi-platform CI/CD Tools ───────────────────────────────────────────
    {
        "name": "get_cicd_logs",
        "description": "Fetch CI/CD pipeline/build logs. Supports: GitHub Actions, GitLab CI, Jenkins, Bamboo, Azure DevOps.",
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "enum": ["github", "gitlab", "jenkins", "bamboo", "azure_devops"]},
                "project_id": {"type": "string", "description": "Project/repo/job identifier"},
                "pipeline_id": {"type": "string", "description": "Pipeline/build/run ID"},
                "additional_params": {"type": "object", "description": "Platform-specific params (e.g., zone, cluster)"},
            },
            "required": ["platform", "project_id"],
        },
    },
    {
        "name": "retry_cicd_pipeline",
        "description": "Retry a failed CI/CD pipeline. Supports: GitLab, Jenkins, Bamboo, Azure DevOps.",
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "enum": ["gitlab", "jenkins", "bamboo", "azure_devops"]},
                "project_id": {"type": "string", "description": "Project/job identifier"},
                "pipeline_id": {"type": "string", "description": "Pipeline/build ID"},
                "additional_params": {"type": "object", "description": "Platform-specific params"},
            },
            "required": ["platform", "project_id"],
        },
    },
    {
        "name": "create_cicd_pr",
        "description": "Create a PR/MR with a CI/CD config fix. Supports: GitHub (via create_github_pr), GitLab, Azure DevOps.",
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "enum": ["github", "gitlab", "azure_devops"]},
                "repo": {"type": "string", "description": "Repository identifier"},
                "file_path": {"type": "string"},
                "new_content": {"type": "string"},
                "pr_title": {"type": "string"},
                "pr_body": {"type": "string"},
                "additional_params": {"type": "object"},
            },
            "required": ["platform", "repo", "file_path", "new_content", "pr_title", "pr_body"],
        },
    },
    # ─── ArgoCD Tools ─────────────────────────────────────────────────────────
    {
        "name": "get_argocd_status",
        "description": "Get ArgoCD application status, health, sync status, and resource details.",
        "input_schema": {
            "type": "object",
            "properties": {
                "app_name": {"type": "string", "description": "ArgoCD application name"},
            },
            "required": ["app_name"],
        },
    },
    {
        "name": "sync_argocd_app",
        "description": "Sync an ArgoCD application. Always use dry_run=true first to preview changes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "app_name": {"type": "string"},
                "prune": {"type": "boolean", "description": "Remove resources not in Git. Default false."},
                "dry_run": {"type": "boolean", "description": "Preview only. Default true."},
            },
            "required": ["app_name"],
        },
    },
    {
        "name": "rollback_argocd_app",
        "description": "Rollback an ArgoCD application to a previous git revision.",
        "input_schema": {
            "type": "object",
            "properties": {
                "app_name": {"type": "string"},
                "revision": {"type": "string", "description": "Git commit SHA. If omitted, rolls back to previous revision."},
            },
            "required": ["app_name"],
        },
    },
    {
        "name": "get_argocd_history",
        "description": "Get deployment history for an ArgoCD application.",
        "input_schema": {
            "type": "object",
            "properties": {
                "app_name": {"type": "string"},
                "limit": {"type": "integer", "description": "Max history items. Default 10."},
            },
            "required": ["app_name"],
        },
    },
    # ─── Cloud Provider Tools ─────────────────────────────────────────────────
    {
        "name": "get_cloud_resource",
        "description": (
            "Get diagnostic info for cloud resources. Supports AWS, GCP, Azure compute, "
            "containers, K8s (EKS/GKE/AKS), load balancers, and more. "
            "Database resources (RDS, Cloud SQL, Azure SQL, Redis, DynamoDB) are OPTIONAL "
            "and disabled by default (ENABLE_DATABASE_COLLECTION=false) for security."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cloud": {"type": "string", "enum": ["aws", "gcp", "azure"]},
                "resource_type": {"type": "string", "description": "e.g., 'ec2', 'ecs', 'gce', 'vm', 'cloud_run'"},
                "resource_id": {"type": "string", "description": "Instance ID, name, etc."},
                "additional_params": {"type": "object", "description": "Cloud-specific params (region, zone, resource_group, cluster)"},
            },
            "required": ["cloud", "resource_type", "resource_id"],
        },
    },
    {
        "name": "restart_cloud_resource",
        "description": "Restart a cloud instance or service (safe operation). Supports: AWS EC2/ECS, GCP GCE/Cloud Run, Azure VM/App Service/Function.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cloud": {"type": "string", "enum": ["aws", "gcp", "azure"]},
                "resource_type": {"type": "string", "description": "e.g., 'ec2', 'ecs', 'gce', 'vm', 'cloud_run', 'app_service', 'function'"},
                "resource_id": {"type": "string"},
                "additional_params": {"type": "object"},
            },
            "required": ["cloud", "resource_type", "resource_id"],
        },
    },
    {
        "name": "scale_cloud_service",
        "description": "Scale a cloud service. Supports: AWS ECS, Azure App Service. (GCP Cloud Run autoscales)",
        "input_schema": {
            "type": "object",
            "properties": {
                "cloud": {"type": "string", "enum": ["aws", "gcp", "azure"]},
                "service_type": {"type": "string"},
                "service_id": {"type": "string"},
                "desired_count": {"type": "integer", "description": "Target instance count (minimum 1)"},
                "additional_params": {"type": "object"},
            },
            "required": ["cloud", "service_type", "service_id", "desired_count"],
        },
    },
]


class DevOpsAgent:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.executor = SafeExecutor()
        
        # K8s and existing tools
        self.k8s_tools = K8sTools()
        self.github_tools = GitHubTools()
        
        # New CI/CD and cloud tools
        self.cicd_tools = CICDTools()
        self.argocd_tools = ArgoCDTools()
        self.cloud_tools = CloudTools()
        
        self.notifier = SlackNotifier()
        
        # Existing collectors
        self.k8s_collector = K8sCollector()
        self.github_collector = GitHubCollector()
        self.server_collector = ServerCollector()
        
        # New CI/CD collectors
        self.gitlab_collector = GitLabCollector()
        self.jenkins_collector = JenkinsCollector()
        self.bamboo_collector = BambooCollector()
        self.azure_devops_collector = AzureDevOpsCollector()
        
        # ArgoCD collector
        self.argocd_collector = ArgoCDCollector()
        
        # Cloud collectors
        self.aws_collector = AWSCollector()
        self.gcp_collector = GCPCollector()
        self.azure_collector = AzureCollector()
        
        self.max_steps = int(os.getenv("MAX_AGENT_STEPS", "10"))
        self.auto_apply = os.getenv("AUTO_APPLY", "false").lower() == "true"
        self._pending_approvals: dict[str, str] = {}

    async def run(self, context: dict) -> dict:
        """Main agent loop: collect context → reason → act → return result."""
        log.info("Agent starting", type=context.get("type"), source=context.get("source"))

        # Enrich context with collected data
        full_context = await self._collect_context(context)

        # Build initial message
        issue_type = context.get("type", "server")
        system_prompt = get_system_prompt(issue_type)

        messages = [
            {
                "role": "user",
                "content": (
                    f"Incident detected. Diagnose and fix this:\n\n"
                    f"```json\n{json.dumps(full_context, indent=2)}\n```\n\n"
                    f"Use tools to gather more context if needed, then apply the fix. "
                    f"Always notify Slack with what you found and what you did."
                ),
            }
        ]

        actions_taken = []
        steps = 0

        # Agentic loop
        while steps < self.max_steps:
            steps += 1
            log.info("Agent step", step=steps)

            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system_prompt,
                tools=AGENT_TOOLS,
                messages=messages,
            )

            # Collect assistant message
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                # Done — extract final text
                final_text = next(
                    (b.text for b in response.content if hasattr(b, "text")), ""
                )
                return {
                    "resolved": True,
                    "diagnosis": final_text,
                    "actions": actions_taken,
                    "steps": steps,
                    "reasoning": final_text,
                }

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    log.info("Tool call", tool=block.name, input=block.input)
                    result = await self._execute_tool(block.name, block.input, context)
                    actions_taken.append({"tool": block.name, "input": block.input, "result": result})

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })

                messages.append({"role": "user", "content": tool_results})
                continue

            break  # Unexpected stop reason

        return {
            "resolved": False,
            "diagnosis": "Max steps reached without resolution",
            "actions": actions_taken,
            "steps": steps,
        }

    async def execute_approved_action(self, incident_id: str, command: str):
        """Execute a command that was approved via Slack."""
        log.info("Executing approved action", incident_id=incident_id, command=command)
        result = await self.executor.run(command)
        await self.notifier.send_message(
            f"✅ Approved action executed for `{incident_id}`:\n```{command}```\nResult: {result.get('stdout', '')}"
        )

    async def _collect_context(self, context: dict) -> dict:
        """Enrich the incident context with collected data."""
        enriched = dict(context)
        issue_type = context.get("type")

        try:
            if issue_type == "k8s" and context.get("namespace"):
                enriched["k8s_data"] = await self.k8s_collector.collect(
                    context.get("namespace"), context.get("pod")
                )
            elif issue_type == "cicd":
                # Determine CI/CD platform
                platform = get_cicd_platform(context.get("labels", {}), context)
                enriched["cicd_platform"] = platform
                
                if platform == "github" and context.get("repo") and context.get("run_id"):
                    enriched["ci_logs"] = await self.github_collector.collect(
                        context["repo"], context["run_id"]
                    )
                elif platform == "gitlab" and context.get("project_id") and context.get("pipeline_id"):
                    enriched["ci_logs"] = await self.gitlab_collector.collect(
                        context["project_id"], context["pipeline_id"]
                    )
                elif platform == "jenkins" and context.get("job_name"):
                    enriched["ci_logs"] = await self.jenkins_collector.collect(
                        context["job_name"], context.get("build_number")
                    )
                elif platform == "bamboo" and context.get("plan_key"):
                    enriched["ci_logs"] = await self.bamboo_collector.collect(
                        context["plan_key"], context.get("build_number")
                    )
                elif platform == "azure_devops" and context.get("project") and context.get("pipeline_id"):
                    enriched["ci_logs"] = await self.azure_devops_collector.collect(
                        context["project"], context["pipeline_id"], context.get("run_id")
                    )
            elif issue_type == "argocd" and context.get("app_name"):
                enriched["argocd_data"] = await self.argocd_collector.collect(context["app_name"])
            elif issue_type == "cloud_aws" and context.get("resource_type") and context.get("resource_id"):
                rt = context["resource_type"]
                blocked = check_database_access(rt, cloud="aws")
                if blocked:
                    enriched["cloud_data"] = blocked
                else:
                    enriched["cloud_data"] = await self.aws_collector.collect(
                        rt, context["resource_id"], **context.get("params", {})
                    )
            elif issue_type == "cloud_gcp" and context.get("resource_type") and context.get("resource_id"):
                rt = context["resource_type"]
                blocked = check_database_access(rt, cloud="gcp")
                if blocked:
                    enriched["cloud_data"] = blocked
                else:
                    enriched["cloud_data"] = await self.gcp_collector.collect(
                        rt, context["resource_id"], **context.get("params", {})
                    )
            elif issue_type == "cloud_azure" and context.get("resource_type") and context.get("resource_id"):
                rt = context["resource_type"]
                blocked = check_database_access(rt, cloud="azure")
                if blocked:
                    enriched["cloud_data"] = blocked
                else:
                    enriched["cloud_data"] = await self.azure_collector.collect(
                        rt, context["resource_id"], **context.get("params", {})
                    )
            elif issue_type == "server":
                enriched["server_data"] = await self.server_collector.collect()
        except Exception as e:
            log.warning("Context collection partial failure", error=str(e))
            enriched["collection_error"] = str(e)

        return enriched

    async def _execute_tool(self, name: str, inputs: dict, context: dict) -> dict:
        """Route tool calls to the appropriate handler."""
        try:
            # ─── Existing K8s Tools ───────────────────────────────────────────
            if name == "get_k8s_context":
                return await self.k8s_collector.collect(
                    inputs.get("namespace", "default"),
                    inputs.get("pod_name"),
                    inputs.get("include_previous", True),
                )
            elif name == "apply_k8s_manifest":
                return await self.k8s_tools.apply_manifest(
                    inputs["manifest_yaml"],
                    dry_run=inputs.get("dry_run", True),
                    namespace=inputs.get("namespace"),
                    auto_apply=self.auto_apply,
                    notifier=self.notifier,
                )
            elif name == "run_kubectl":
                return await self.k8s_tools.run_kubectl(inputs["command"], auto_apply=self.auto_apply)
            elif name == "rollback_deployment":
                return await self.k8s_tools.rollback(
                    inputs["deployment"], inputs["namespace"],
                    revision=inputs.get("revision"),
                    auto_apply=self.auto_apply,
                    notifier=self.notifier,
                )
            
            # ─── Existing GitHub/Server Tools ─────────────────────────────────
            elif name == "get_github_logs":
                return await self.github_collector.collect(inputs["repo"], inputs["run_id"])
            elif name == "create_github_pr":
                return await self.github_tools.create_fix_pr(
                    inputs["repo"], inputs["file_path"],
                    inputs["new_content"], inputs["pr_title"], inputs["pr_body"],
                )
            elif name == "run_shell_command":
                return await self.executor.run_safe(inputs["command"], host=inputs.get("host"))
            
            # ─── Multi-platform CI/CD Tools ────────────────────────────────────
            elif name == "get_cicd_logs":
                platform = inputs["platform"]
                project_id = inputs["project_id"]
                pipeline_id = inputs.get("pipeline_id")
                params = inputs.get("additional_params", {})
                
                if platform == "github":
                    return await self.github_collector.collect(project_id, int(pipeline_id))
                elif platform == "gitlab":
                    return await self.gitlab_collector.collect(project_id, int(pipeline_id))
                elif platform == "jenkins":
                    return await self.jenkins_collector.collect(project_id, int(pipeline_id) if pipeline_id else None)
                elif platform == "bamboo":
                    return await self.bamboo_collector.collect(project_id, int(pipeline_id) if pipeline_id else None)
                elif platform == "azure_devops":
                    return await self.azure_devops_collector.collect(
                        params.get("project", project_id),
                        int(params.get("pipeline_id", pipeline_id)),
                        int(params.get("run_id", pipeline_id))
                    )
                else:
                    return {"error": f"Unsupported CI/CD platform: {platform}"}
            
            elif name == "retry_cicd_pipeline":
                platform = inputs["platform"]
                return await self.cicd_tools.retry_pipeline(
                    platform, inputs["project_id"], inputs.get("pipeline_id"),
                    **inputs.get("additional_params", {})
                )
            
            elif name == "create_cicd_pr":
                platform = inputs["platform"]
                if platform == "github":
                    # Use existing GitHub tool
                    return await self.github_tools.create_fix_pr(
                        inputs["repo"], inputs["file_path"],
                        inputs["new_content"], inputs["pr_title"], inputs["pr_body"]
                    )
                else:
                    return await self.cicd_tools.create_fix_pr(
                        platform, inputs["repo"], inputs["file_path"],
                        inputs["new_content"], inputs["pr_title"], inputs["pr_body"],
                        **inputs.get("additional_params", {})
                    )
            
            # ─── ArgoCD Tools ──────────────────────────────────────────────────
            elif name == "get_argocd_status":
                return await self.argocd_tools.get_application_status(inputs["app_name"])
            
            elif name == "sync_argocd_app":
                return await self.argocd_tools.sync_application(
                    inputs["app_name"],
                    prune=inputs.get("prune", False),
                    dry_run=inputs.get("dry_run", True),
                    auto_apply=self.auto_apply,
                    notifier=self.notifier
                )
            
            elif name == "rollback_argocd_app":
                return await self.argocd_tools.rollback_application(
                    inputs["app_name"],
                    revision=inputs.get("revision"),
                    auto_apply=self.auto_apply,
                    notifier=self.notifier
                )
            
            elif name == "get_argocd_history":
                return await self.argocd_tools.get_application_history(
                    inputs["app_name"],
                    limit=inputs.get("limit", 10)
                )
            
            # ─── Cloud Provider Tools ──────────────────────────────────────────
            elif name == "get_cloud_resource":
                cloud = inputs["cloud"]
                resource_type = inputs["resource_type"]
                resource_id = inputs["resource_id"]
                params = inputs.get("additional_params", {})

                blocked = check_database_access(resource_type, cloud=cloud)
                if blocked:
                    return blocked

                if cloud == "aws":
                    return await self.aws_collector.collect(resource_type, resource_id, **params)
                elif cloud == "gcp":
                    return await self.gcp_collector.collect(resource_type, resource_id, **params)
                elif cloud == "azure":
                    return await self.azure_collector.collect(resource_type, resource_id, **params)
                else:
                    return {"error": f"Unsupported cloud: {cloud}"}
            
            elif name == "restart_cloud_resource":
                cloud = inputs["cloud"]
                resource_type = inputs["resource_type"]
                resource_id = inputs["resource_id"]
                params = inputs.get("additional_params", {})
                
                if resource_type in ["instance", "ec2", "gce", "vm"]:
                    return await self.cloud_tools.restart_instance(cloud, resource_id, **params)
                else:
                    return await self.cloud_tools.restart_service(cloud, resource_type, resource_id, **params)
            
            elif name == "scale_cloud_service":
                return await self.cloud_tools.scale_service(
                    inputs["cloud"],
                    inputs["service_type"],
                    inputs["service_id"],
                    inputs["desired_count"],
                    **inputs.get("additional_params", {})
                )
            
            # ─── Notifications ─────────────────────────────────────────────────
            elif name == "notify_slack":
                await self.notifier.send_message(
                    inputs["message"],
                    severity=inputs.get("severity", "info"),
                    resolved=inputs.get("resolved", False),
                    requires_approval=inputs.get("requires_approval", False),
                    approval_command=inputs.get("approval_command"),
                )
                return {"sent": True}

            else:
                return {"error": f"Unknown tool: {name}"}

        except Exception as e:
            log.error("Tool execution error", tool=name, error=str(e))
            return {"error": str(e)}
