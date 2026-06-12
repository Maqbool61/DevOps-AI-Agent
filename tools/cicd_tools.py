"""
CI/CD Tools for GitLab, Jenkins, Bamboo, Azure DevOps
Provides safe operations for CI/CD platforms.
"""
import os
from typing import Optional

import httpx
import structlog

log = structlog.get_logger()


class CICDTools:
    """Unified CI/CD tools for multiple platforms."""
    
    def __init__(self):
        self.gitlab_token = os.getenv("GITLAB_TOKEN", "")
        self.gitlab_url = os.getenv("GITLAB_URL", "https://gitlab.com")
        self.jenkins_url = os.getenv("JENKINS_URL", "")
        self.jenkins_username = os.getenv("JENKINS_USERNAME", "")
        self.jenkins_token = os.getenv("JENKINS_API_TOKEN", "")
        self.bamboo_url = os.getenv("BAMBOO_URL", "")
        self.bamboo_username = os.getenv("BAMBOO_USERNAME", "")
        self.bamboo_password = os.getenv("BAMBOO_PASSWORD", "")
        self.azure_org = os.getenv("AZURE_DEVOPS_ORG", "")
        self.azure_pat = os.getenv("AZURE_DEVOPS_PAT", "")

    async def retry_pipeline(
        self,
        platform: str,
        project_id: str,
        pipeline_id: Optional[str] = None,
        **kwargs
    ) -> dict:
        """
        Retry a failed pipeline/build.
        
        Args:
            platform: 'gitlab', 'jenkins', 'bamboo', 'azure_devops'
            project_id: Project/job identifier
            pipeline_id: Pipeline/build identifier (optional for some platforms)
        """
        if platform == "gitlab":
            return await self._retry_gitlab_pipeline(project_id, int(pipeline_id))
        elif platform == "jenkins":
            return await self._retry_jenkins_build(project_id)
        elif platform == "bamboo":
            return await self._retry_bamboo_build(project_id)
        elif platform == "azure_devops":
            return await self._retry_azure_pipeline(
                kwargs.get("project"),
                int(pipeline_id),
                int(kwargs.get("run_id"))
            )
        else:
            return {"error": f"Unsupported platform: {platform}"}

    async def create_fix_pr(
        self,
        platform: str,
        repo: str,
        file_path: str,
        new_content: str,
        pr_title: str,
        pr_body: str,
        **kwargs
    ) -> dict:
        """
        Create a PR/MR with a fix.
        
        Args:
            platform: 'gitlab', 'azure_devops' (GitHub uses existing tool)
            repo: Repository identifier
            file_path: File to update
            new_content: New file content
            pr_title: PR/MR title
            pr_body: PR/MR description
        """
        if platform == "gitlab":
            return await self._create_gitlab_mr(
                repo, file_path, new_content, pr_title, pr_body
            )
        elif platform == "azure_devops":
            return await self._create_azure_pr(
                kwargs.get("project"),
                repo,
                file_path,
                new_content,
                pr_title,
                pr_body
            )
        else:
            return {"error": f"PR creation not supported for {platform}"}

    # ─── GitLab ───────────────────────────────────────────────────────────────

    async def _retry_gitlab_pipeline(self, project_id: str, pipeline_id: int) -> dict:
        """Retry a failed GitLab pipeline."""
        if not self.gitlab_token:
            return {"error": "GITLAB_TOKEN not configured"}

        url = f"{self.gitlab_url}/api/v4/projects/{project_id}/pipelines/{pipeline_id}/retry"
        headers = {"PRIVATE-TOKEN": self.gitlab_token}

        async with httpx.AsyncClient(headers=headers, timeout=30) as client:
            try:
                resp = await client.post(url)
                if resp.status_code in [200, 201]:
                    return {
                        "success": True,
                        "message": f"GitLab pipeline {pipeline_id} retry triggered",
                        "pipeline": resp.json(),
                    }
                else:
                    return {"error": f"Failed to retry pipeline: {resp.status_code}"}
            except Exception as e:
                return {"error": str(e)}

    async def _create_gitlab_mr(
        self, project_id: str, file_path: str, new_content: str, title: str, description: str
    ) -> dict:
        """Create a GitLab merge request with a fix."""
        if not self.gitlab_token:
            return {"error": "GITLAB_TOKEN not configured"}

        headers = {"PRIVATE-TOKEN": self.gitlab_token, "Content-Type": "application/json"}
        base_url = f"{self.gitlab_url}/api/v4/projects/{project_id}"

        async with httpx.AsyncClient(headers=headers, timeout=60) as client:
            try:
                # 1. Get default branch
                project_resp = await client.get(base_url)
                default_branch = project_resp.json().get("default_branch", "main")

                # 2. Create a new branch
                branch_name = f"fix-{file_path.replace('/', '-')}-{__import__('time').time_ns()}"
                create_branch_resp = await client.post(
                    f"{base_url}/repository/branches",
                    json={"branch": branch_name, "ref": default_branch}
                )
                
                if create_branch_resp.status_code not in [200, 201]:
                    return {"error": f"Failed to create branch: {create_branch_resp.status_code}"}

                # 3. Update file
                import base64
                content_b64 = base64.b64encode(new_content.encode()).decode()
                
                update_resp = await client.put(
                    f"{base_url}/repository/files/{file_path.replace('/', '%2F')}",
                    json={
                        "branch": branch_name,
                        "content": content_b64,
                        "commit_message": f"Fix: {title}",
                        "encoding": "base64",
                    }
                )
                
                if update_resp.status_code not in [200, 201]:
                    return {"error": f"Failed to update file: {update_resp.status_code}"}

                # 4. Create MR
                mr_resp = await client.post(
                    f"{base_url}/merge_requests",
                    json={
                        "source_branch": branch_name,
                        "target_branch": default_branch,
                        "title": title,
                        "description": description,
                    }
                )
                
                if mr_resp.status_code in [200, 201]:
                    mr_data = mr_resp.json()
                    return {
                        "success": True,
                        "merge_request_url": mr_data.get("web_url"),
                        "merge_request_iid": mr_data.get("iid"),
                        "branch": branch_name,
                    }
                else:
                    return {"error": f"Failed to create MR: {mr_resp.status_code}"}

            except Exception as e:
                return {"error": str(e)}

    # ─── Jenkins ──────────────────────────────────────────────────────────────

    async def _retry_jenkins_build(self, job_name: str) -> dict:
        """Trigger a new Jenkins build."""
        if not self.jenkins_url:
            return {"error": "JENKINS_URL not configured"}

        url = f"{self.jenkins_url}/job/{job_name}/build"
        auth = (self.jenkins_username, self.jenkins_token) if self.jenkins_username else None

        async with httpx.AsyncClient(auth=auth, timeout=30) as client:
            try:
                resp = await client.post(url)
                if resp.status_code in [200, 201]:
                    return {
                        "success": True,
                        "message": f"Jenkins job {job_name} build triggered",
                    }
                else:
                    return {"error": f"Failed to trigger build: {resp.status_code}"}
            except Exception as e:
                return {"error": str(e)}

    # ─── Bamboo ───────────────────────────────────────────────────────────────

    async def _retry_bamboo_build(self, plan_key: str) -> dict:
        """Trigger a new Bamboo build."""
        if not self.bamboo_url:
            return {"error": "BAMBOO_URL not configured"}

        url = f"{self.bamboo_url}/rest/api/latest/queue/{plan_key}"
        auth = (self.bamboo_username, self.bamboo_password) if self.bamboo_username else None

        async with httpx.AsyncClient(auth=auth, timeout=30) as client:
            try:
                resp = await client.post(url)
                if resp.status_code in [200, 201]:
                    return {
                        "success": True,
                        "message": f"Bamboo plan {plan_key} build queued",
                    }
                else:
                    return {"error": f"Failed to queue build: {resp.status_code}"}
            except Exception as e:
                return {"error": str(e)}

    # ─── Azure DevOps ─────────────────────────────────────────────────────────

    async def _retry_azure_pipeline(self, project: str, pipeline_id: int, run_id: int) -> dict:
        """Retry a failed Azure DevOps pipeline."""
        if not self.azure_org or not self.azure_pat:
            return {"error": "AZURE_DEVOPS_ORG and AZURE_DEVOPS_PAT not configured"}

        import base64
        auth_string = f":{self.azure_pat}"
        auth_b64 = base64.b64encode(auth_string.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json",
        }

        url = f"https://dev.azure.com/{self.azure_org}/{project}/_apis/pipelines/{pipeline_id}/runs?api-version=7.0"

        async with httpx.AsyncClient(headers=headers, timeout=30) as client:
            try:
                # Trigger a new run
                resp = await client.post(url, json={})
                if resp.status_code in [200, 201]:
                    run_data = resp.json()
                    return {
                        "success": True,
                        "message": f"Azure pipeline {pipeline_id} run triggered",
                        "run_id": run_data.get("id"),
                        "url": run_data.get("url"),
                    }
                else:
                    return {"error": f"Failed to trigger pipeline: {resp.status_code}"}
            except Exception as e:
                return {"error": str(e)}

    async def _create_azure_pr(
        self, project: str, repo: str, file_path: str, new_content: str, title: str, description: str
    ) -> dict:
        """Create an Azure DevOps pull request with a fix."""
        if not self.azure_org or not self.azure_pat:
            return {"error": "AZURE_DEVOPS_ORG and AZURE_DEVOPS_PAT not configured"}

        import base64
        auth_string = f":{self.azure_pat}"
        auth_b64 = base64.b64encode(auth_string.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json",
        }

        base_url = f"https://dev.azure.com/{self.azure_org}/{project}/_apis/git/repositories/{repo}"

        async with httpx.AsyncClient(headers=headers, timeout=60) as client:
            try:
                # Simplified: This is a complex operation that requires:
                # 1. Get default branch
                # 2. Create new branch
                # 3. Push changes
                # 4. Create PR
                # For now, return a message indicating manual intervention
                return {
                    "success": False,
                    "message": "Azure DevOps PR creation requires manual intervention or Git operations",
                    "note": "Consider using Git commands to create branch and push changes, then create PR via API",
                }
            except Exception as e:
                return {"error": str(e)}
