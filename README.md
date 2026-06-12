# 🤖 DevOps AI Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/yourusername/devops-ai-agent/workflows/CI/badge.svg)](https://github.com/yourusername/devops-ai-agent/actions)

An autonomous **AI-powered DevOps agent** that monitors, diagnoses, and fixes incidents across your entire infrastructure stack — automatically. Built for **SRE teams** who want to reduce toil and improve MTTR (Mean Time To Recovery).

## 🎯 Built For SRE & DevOps Teams

This agent is your **24/7 on-call teammate** that handles:

- **CI/CD Pipeline Failures** (GitHub Actions, GitLab CI, Jenkins, Azure DevOps, Bamboo)
- **Kubernetes Issues** (CrashLoopBackOff, OOMKilled, ImagePullBackOff, ConfigMap errors)
- **Cloud Infrastructure** (AWS EC2/ECS/Lambda, GCP GCE/Cloud Run, Azure VMs/AKS)
- **GitOps Deployments** (ArgoCD sync failures, rollbacks)
- **Container Builds** (Dockerfile optimization, build errors)
- **Server Issues** (systemd failures, disk/CPU/memory alerts)

### Why This Agent?

- **Reduce Alert Fatigue**: Let AI handle repetitive incidents
- **Faster MTTR**: Automated diagnosis → remediation in minutes
- **Learn from Operations**: Full audit trail of every decision
- **Safe by Default**: Dry-run first, approval gates, command whitelisting
- **Plugin Architecture**: Easy to extend with custom collectors and tools

---

## 🏗️ Architecture

```
┌─────────────────┐
│  Alert Sources  │
│                 │
│  • CI/CD        │
│  • Prometheus   │
│  • CloudWatch   │
│  • PagerDuty    │
│  • Custom       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Webhook API    │
│  (FastAPI)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐       ┌──────────────────┐
│ Log Collectors  │──────▶│  Claude AI Agent │
│  (Plugins)      │       │  (Reasoning Loop)│
│                 │       └─────────┬────────┘
│  • K8s          │                 │
│  • CI/CD        │                 ▼
│  • Cloud        │       ┌──────────────────┐
│  • ArgoCD       │       │   Tool Executor  │
│  • Docker       │       │   (Safe Actions) │
│  • Server       │       └─────────┬────────┘
└─────────────────┘                 │
                                    ▼
                          ┌──────────────────┐
                          │  Notifications   │
                          │  • Slack         │
                          │  • Audit Log     │
                          │  • PagerDuty     │
                          └──────────────────┘
```

---

## ⚠️ Safety-First Approach

```
🛡️ NEVER DELETE. NEVER DESTROY. NOTIFY INSTEAD.
```

This agent follows **strict safety principles**:
- ✅ **Email alerts for dangerous operations** - Never executes delete/destroy commands
- ✅ **Approval gates** - Human oversight required for critical actions
- ✅ **Dry-run by default** - Test before executing
- ✅ **Comprehensive audit trail** - Every decision logged
- ✅ **Security scanning** - Automatic vulnerability detection
- ✅ **Compliance checks** - Validate against DevSecOps standards

**Read [SECURITY_POLICY.md](SECURITY_POLICY.md) before deployment.**

---

## ✨ Key Features

### 🔌 Plugin-Based Architecture

Easily extend with custom collectors and tools:

```python
# Add a new platform in 3 steps:

# 1. Create collector (collectors/my_platform.py)
class MyPlatformCollector:
    def collect(self, incident_data):
        return {"logs": "...", "context": "..."}

# 2. Define tools (tools/my_platform_tools.py)
def my_platform_action(params):
    return {"status": "success"}

# 3. Register in agent/core.py
self.collectors['my_platform'] = MyPlatformCollector()
```

### 🛡️ Production-Ready Safety & DevSecOps

**Core Safety**:
- **Dangerous operations BLOCKED**: No deletion, no termination, no data loss
- **Email notifications**: Alerts sent for operations requiring manual intervention
- **Dry-run by default**: Preview changes before applying
- **Multi-level approval gates**: Human oversight for critical actions
- **Command blacklist**: Destructive commands permanently blocked
- **Audit trail**: Every decision logged with AI reasoning

**DevSecOps Features**:
- **Security scanning**: Detects vulnerabilities, exposed secrets, misconfigurations
- **Compliance validation**: CIS Benchmark, SOC 2, PCI-DSS, HIPAA
- **Container security**: Privileged containers, root user, security context checks
- **RBAC enforcement**: Least-privilege access controls
- **Emergency stop**: Kill switch for immediate shutdown

**See [SECURITY_POLICY.md](SECURITY_POLICY.md) and [DEVSECOPS_GUIDE.md](DEVSECOPS_GUIDE.md) for details.**

### 🚀 Multi-Platform Support

| Category | Supported Platforms |
|----------|-------------------|
| **CI/CD** | GitHub Actions, GitLab CI, Jenkins, Azure DevOps, Bamboo |
| **Cloud** | AWS (EC2, ECS, Lambda, RDS), GCP (GCE, Cloud Run, Functions), Azure (VMs, AKS, Functions) |
| **Containers** | Kubernetes, Docker, ArgoCD |
| **Monitoring** | Prometheus Alertmanager, CloudWatch, Azure Monitor |
| **Notifications** | Slack, PagerDuty |

### 🧠 Intelligent Automation

- **Context-aware**: Collects relevant logs, metrics, and configs
- **Root cause analysis**: Understands error patterns across platforms
- **Self-correcting**: Verifies fixes and retries if needed
- **Learning**: Improves from past incidents (audit log analysis)

---

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- `kubectl` (for K8s features)
- Cloud CLI tools (optional): `aws`, `gcloud`, `az`

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/devops-ai-agent.git
cd devops-ai-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install core dependencies
pip install -r requirements.txt

# Install cloud providers (optional)
pip install boto3                    # AWS
pip install google-cloud-compute     # GCP
pip install azure-mgmt-compute       # Azure
```

### 2. Configuration

```bash
# Copy example configuration
cp .env.example .env

# Edit configuration (required)
nano .env
```

**Minimum required variables:**

```bash
# AI Provider
ANTHROPIC_API_KEY=your-claude-api-key

# Email Alerts (CRITICAL - for dangerous operation notifications)
EMAIL_ENABLED=true
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_SMTP_USER=devops-agent@yourcompany.com
EMAIL_SMTP_PASSWORD=your-app-password
EMAIL_FROM=devops-agent@yourcompany.com
EMAIL_TO=sre-team@yourcompany.com

# Notifications
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
SLACK_APPROVAL_CHANNEL=devops-approvals

# Source Control
GITHUB_TOKEN=ghp_...

# Safety Settings (IMPORTANT - read SECURITY_POLICY.md)
AUTO_APPLY=false  # Keep false - requires approval for all actions
AGENT_EMERGENCY_STOP=false  # Set true to disable agent
ENABLE_SECURITY_SCANNING=true
ENABLE_COMPLIANCE_CHECKS=true
```

**⚠️ IMPORTANT**: Configure email alerts BEFORE deployment. The agent sends email notifications for dangerous operations that require manual intervention.

See [.env.example](.env.example) for all configuration options.

### 3. Run Locally

```bash
# Start the agent API server
uvicorn api.server:app --reload --port 8000

# In another terminal, test with a manual incident
curl -X POST http://localhost:8000/webhook/manual \
  -H "Content-Type: application/json" \
  -d '{
    "type": "k8s",
    "namespace": "default",
    "pod_name": "myapp-pod",
    "labels": {"severity": "critical"}
  }'

# Check the audit log
curl http://localhost:8000/audit
```

### 4. Deploy to Kubernetes

```bash
# Create namespace
kubectl create namespace devops-agent

# Create secret with credentials
kubectl create secret generic agent-secrets \
  --from-literal=ANTHROPIC_API_KEY=your-key \
  --from-literal=GITHUB_TOKEN=your-token \
  --from-literal=SLACK_WEBHOOK_URL=your-webhook \
  -n devops-agent

# Deploy the agent
kubectl apply -f k8s/ -n devops-agent

# Verify deployment
kubectl get pods -n devops-agent
kubectl logs -f deployment/devops-agent -n devops-agent
```

---

## 📋 Usage Examples

### Kubernetes CrashLoopBackOff

**Alert**: Pod `web-app` in `production` namespace crashing

**Agent Actions**:
1. Fetches pod logs, events, and manifest
2. Identifies missing `ConfigMap` reference
3. Creates ConfigMap from template
4. Restarts pod
5. Verifies pod is running
6. Notifies team in Slack

### CI/CD Pipeline Failure

**Alert**: GitLab CI pipeline failed on merge to `main`

**Agent Actions**:
1. Fetches pipeline logs and failed job output
2. Detects missing environment variable
3. Creates merge request to add variable to `.gitlab-ci.yml`
4. Retries pipeline
5. Confirms build passes
6. Notifies team

### AWS ECS Task Failure

**Alert**: ECS task stopped with `OutOfMemory` error

**Agent Actions**:
1. Fetches CloudWatch logs and task definition
2. Analyzes memory usage pattern
3. Proposes updated task definition with increased memory
4. **Waits for approval** (safe operation)
5. Updates service with new definition
6. Monitors healthy deployment

---

## 🔧 Configuration

### Platform Setup Guides

Detailed guides for each platform:

- [Multi-Platform Guide](MULTI_PLATFORM_GUIDE.md) - Complete configuration reference
- [GitHub Actions Setup](#github-actions)
- [Kubernetes RBAC](#kubernetes-rbac)
- [Cloud Provider Auth](#cloud-provider-authentication)

### Webhook Configuration

Configure your monitoring tools to send alerts to the agent:

#### Prometheus Alertmanager

```yaml
# alertmanager.yml
route:
  receiver: 'devops-agent'

receivers:
  - name: 'devops-agent'
    webhook_configs:
      - url: 'http://devops-agent.devops-agent.svc.cluster.local:8000/webhook/alertmanager'
        send_resolved: true
```

#### GitHub Actions

```
Repository Settings → Webhooks → Add webhook
URL: https://your-agent-domain.com/webhook/github
Content type: application/json
Events: Workflow runs
```

#### PagerDuty

Use the Generic Webhooks integration pointing to `/webhook/pagerduty`

---

## 🧪 Testing

```bash
# Run unit tests
pytest tests/

# Test with dummy incidents (no cloud credentials needed)
python scripts/simulate_incident.py --type k8s
python scripts/simulate_incident.py --type cicd --platform gitlab

# Test in dry-run mode
export AUTO_APPLY=false
# Agent will show proposed actions without executing
```

See [CI pipeline](.github/workflows/ci.yml) for automated testing.

---

## 📊 Monitoring & Observability

### Health Check

```bash
curl http://localhost:8000/health
```

### Audit Log

All agent decisions are logged:

```bash
curl http://localhost:8000/audit | jq '.'
```

### Metrics (Optional)

The agent exposes Prometheus metrics at `/metrics`:

```
agent_incidents_total{type="k8s",resolved="true"} 42
agent_tool_calls_total{tool="kubectl_apply"} 18
agent_approval_requests_total{approved="true"} 12
```

---

## 🔌 Extending the Agent

### Add a Custom Collector

```python
# collectors/my_platform.py
class MyPlatformCollector:
    """Collects logs from MyPlatform"""
    
    def __init__(self, api_token):
        self.client = MyPlatformClient(token=api_token)
    
    def collect(self, incident_data: dict) -> dict:
        """
        Args:
            incident_data: {
                "resource_id": "...",
                "timestamp": "...",
            }
        
        Returns:
            {
                "logs": [...],
                "metadata": {...},
                "recent_changes": [...]
            }
        """
        logs = self.client.get_logs(incident_data['resource_id'])
        return {
            "logs": logs,
            "metadata": {...}
        }
```

### Add a Custom Tool

```python
# tools/my_platform_tools.py
def restart_my_service(service_id: str, dry_run: bool = True) -> dict:
    """
    Restarts a service in MyPlatform
    
    Args:
        service_id: Service identifier
        dry_run: If True, only simulate the restart
    
    Returns:
        {"status": "success", "message": "...", "dry_run": True}
    """
    if dry_run:
        return {
            "status": "success",
            "message": f"Would restart service {service_id}",
            "dry_run": True
        }
    
    # Actual restart logic
    client = MyPlatformClient()
    result = client.restart_service(service_id)
    
    return {
        "status": "success" if result else "failed",
        "message": f"Restarted service {service_id}",
        "dry_run": False
    }
```

### Register in Agent

```python
# agent/core.py
from collectors.my_platform import MyPlatformCollector
from tools.my_platform_tools import restart_my_service

class DevOpsAgent:
    def __init__(self):
        # Register collector
        self.collectors['my_platform'] = MyPlatformCollector(
            api_token=os.getenv('MY_PLATFORM_TOKEN')
        )
        
        # Register tool
        self.tools.append({
            "name": "restart_my_service",
            "description": "Restarts a service in MyPlatform",
            "input_schema": {
                "type": "object",
                "properties": {
                    "service_id": {"type": "string"},
                    "dry_run": {"type": "boolean", "default": True}
                },
                "required": ["service_id"]
            }
        })
```

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Code style guidelines
- Testing requirements
- PR process
- Development setup

### Development Setup

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run linting
black .
flake8 .
mypy .

# Run tests with coverage
pytest --cov=. tests/
```

---

## 📖 Documentation

### Essential Reading
- **[SECURITY_POLICY.md](SECURITY_POLICY.md)** - ⚠️ **READ FIRST** - Safety rules and blocked operations
- **[DEVSECOPS_GUIDE.md](DEVSECOPS_GUIDE.md)** - DevSecOps best practices and compliance
- **[GETTING_STARTED.md](GETTING_STARTED.md)** - Quick start guide (15 minutes)

### Detailed Guides
- [Multi-Platform Guide](MULTI_PLATFORM_GUIDE.md) - Complete platform configuration
- [Deployment Guide](DEPLOYMENT.md) - Production deployment for K8s, AWS, GCP, Azure
- [Architecture](ARCHITECTURE.md) - System design and architecture
- [Contributing](CONTRIBUTING.md) - How to contribute
- [Extension Summary](EXTENSION_SUMMARY.md) - Recent changes and features

---

## 🛡️ Security

### Best Practices

1. **Start with `AUTO_APPLY=false`**: Review agent decisions for 1-2 weeks
2. **Use least-privilege credentials**: Limit IAM/RBAC permissions
3. **Namespace isolation**: Restrict K8s operations to specific namespaces
4. **Audit regularly**: Review `/audit` logs weekly
5. **Rotate secrets**: Use short-lived tokens where possible

### Reporting Security Issues

Please report security vulnerabilities to: security@yourorg.com

Do not open public issues for security concerns.

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Built with [Anthropic Claude](https://www.anthropic.com/claude) for AI reasoning
- Inspired by the SRE community and incident response best practices
- Thanks to all contributors!

---

## 📬 Support & Community

- **Issues**: [GitHub Issues](https://github.com/yourusername/devops-ai-agent/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/devops-ai-agent/discussions)
- **Slack**: [Join our community](https://your-slack-invite.link)

---

## 🗺️ Roadmap

- [ ] More CI/CD platforms (CircleCI, TeamCity, Drone CI)
- [ ] Database diagnostics (PostgreSQL, MySQL, MongoDB)
- [ ] Cost optimization recommendations
- [ ] Security vulnerability scanning
- [ ] Integration with Datadog, New Relic, Grafana
- [ ] Custom runbooks and playbooks
- [ ] Multi-agent collaboration

---

**Made with ❤️ by the DevOps community**

*Reduce toil. Ship faster. Sleep better.*
