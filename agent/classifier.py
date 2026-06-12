"""
Issue type classifier — maps alert names and labels to issue types.
Supports multiple CI/CD platforms, cloud providers, and ArgoCD.
"""


def classify_issue(alertname: str, labels: dict) -> str:
    """
    Classify incident type based on alert name and labels.
    
    Returns:
        - k8s: Kubernetes/container issues
        - cicd: CI/CD pipeline issues (GitHub, GitLab, Jenkins, Bamboo, Azure DevOps)
        - server: Server/VM issues
        - cloud_aws: AWS resource issues
        - cloud_gcp: GCP resource issues
        - cloud_azure: Azure resource issues
        - argocd: ArgoCD deployment issues
    """
    name = alertname.lower()

    k8s_keywords = ["pod", "container", "crash", "oom", "image", "evict",
                    "pending", "replicaset", "deployment", "statefulset", "daemonset"]
    
    server_keywords = ["cpu", "memory", "disk", "load", "nginx", "apache",
                       "service", "host", "node", "network", "ssh", "systemd"]
    
    cicd_keywords = ["deploy", "pipeline", "build", "ci", "release", "workflow",
                     "jenkins", "gitlab", "bamboo", "azure-pipeline", "github-actions"]
    
    argocd_keywords = ["argocd", "argo", "gitops", "sync"]
    
    aws_keywords = ["ec2", "ecs", "lambda", "rds", "aws", "cloudwatch", "elb", "alb"]
    
    gcp_keywords = ["gce", "gke", "cloud-run", "cloud-function", "gcp", "google-cloud"]
    
    azure_keywords = ["azure-vm", "aks", "app-service", "azure-function", "azure-sql"]

    # Check ArgoCD first (most specific)
    if any(k in name for k in argocd_keywords):
        return "argocd"
    
    # Check cloud providers
    if any(k in name for k in aws_keywords):
        return "cloud_aws"
    if any(k in name for k in gcp_keywords):
        return "cloud_gcp"
    if any(k in name for k in azure_keywords):
        return "cloud_azure"
    
    # Check K8s
    if any(k in name for k in k8s_keywords):
        return "k8s"
    
    # Check CI/CD
    if any(k in name for k in cicd_keywords):
        return "cicd"
    
    # Check server
    if any(k in name for k in server_keywords):
        return "server"

    # Fallback: check labels
    if labels.get("namespace") or labels.get("pod"):
        return "k8s"
    if labels.get("pipeline") or labels.get("job"):
        return "cicd"
    if labels.get("argocd_app"):
        return "argocd"
    if labels.get("cloud_provider"):
        cloud = labels["cloud_provider"].lower()
        if "aws" in cloud:
            return "cloud_aws"
        elif "gcp" in cloud or "google" in cloud:
            return "cloud_gcp"
        elif "azure" in cloud:
            return "cloud_azure"

    return "server"


def get_cicd_platform(labels: dict, context: dict) -> str:
    """
    Determine the specific CI/CD platform from labels and context.
    
    Returns: 'github', 'gitlab', 'jenkins', 'bamboo', 'azure_devops', or 'unknown'
    """
    # Check labels first
    if labels.get("cicd_platform"):
        return labels["cicd_platform"].lower()
    
    # Check context/source
    source = context.get("source", "").lower()
    if "github" in source:
        return "github"
    elif "gitlab" in source:
        return "gitlab"
    elif "jenkins" in source:
        return "jenkins"
    elif "bamboo" in source:
        return "bamboo"
    elif "azure" in source or "azuredevops" in source:
        return "azure_devops"
    
    # Check repo or job URL
    repo_url = context.get("repo", "") or labels.get("repo_url", "")
    if "github.com" in repo_url:
        return "github"
    elif "gitlab" in repo_url:
        return "gitlab"
    
    return "unknown"
