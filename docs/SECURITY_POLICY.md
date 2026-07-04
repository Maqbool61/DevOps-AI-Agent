# Security Policy

## 🛡️ Safety-First Philosophy

The DevOps AI Agent follows a **strict safety-first approach**:

```
NEVER DELETE. NEVER DESTROY. NOTIFY INSTEAD.
```

## Core Safety Principles

### 1. No Destructive Operations

The agent will **NEVER** execute:
- ❌ Delete resources (pods, deployments, instances, databases)
- ❌ Drop databases or tables
- ❌ Format disks or storage
- ❌ Terminate instances
- ❌ Remove files or directories
- ❌ Force operations that bypass safety checks
- ❌ Rollback to unknown states
- ❌ Scale to zero (kills services)
- ❌ Modify production without approval
- ❌ Change security groups or firewalls without review

### 2. Notification Over Action

For any dangerous operation, the agent will:
1. ✅ Detect the need for a potentially dangerous action
2. ✅ Send email notification to operations team
3. ✅ Send Slack alert with full context
4. ✅ Log the recommendation in audit trail
5. ✅ Provide manual commands for human execution
6. ✅ Wait for human approval

### 3. Read-Only by Default

Most operations are **read-only**:
- ✅ Fetch logs and metrics
- ✅ Describe resource status
- ✅ Run diagnostic queries
- ✅ Generate reports
- ✅ Analyze configurations

## Allowed Operations

### Safe Auto-Remediation (After Approval)

The agent can automatically perform these **safe** operations:

#### Kubernetes
- ✅ Restart pods (does not delete)
- ✅ Scale deployments UP (never down to 0)
- ✅ Apply ConfigMaps (version controlled)
- ✅ Update labels and annotations
- ✅ Rollback to previous known-good version
- ⚠️ Always runs dry-run first
- ⚠️ Never modifies PersistentVolumes

#### CI/CD
- ✅ Retry failed builds
- ✅ Create pull/merge requests
- ✅ Update pipeline configurations
- ✅ Cancel stuck pipelines
- ⚠️ Never deletes branches
- ⚠️ Never force-pushes

#### Cloud Resources
- ✅ Restart services (graceful restart)
- ✅ Scale services UP (never down)
- ✅ Update service configurations
- ✅ Rotate logs
- ⚠️ Never terminates instances
- ⚠️ Never modifies security groups

#### Applications
- ✅ Restart application processes
- ✅ Clear caches
- ✅ Reload configurations
- ✅ Health check endpoints
- ⚠️ Never stops services
- ⚠️ Never modifies databases

## Blocked Operations

### Permanently Blocked Commands

```yaml
blocked_operations:
  # Deletion
  - delete
  - remove
  - rm -rf
  - drop
  - destroy
  - terminate
  - purge
  - prune
  - clean
  - wipe
  
  # Formatting/Destructive
  - format
  - mkfs
  - dd if=/dev/zero
  
  # Force operations
  - --force
  - -f (when used with delete)
  - --force-delete
  - --cascade=true (when deleting)
  
  # Database
  - DROP DATABASE
  - DROP TABLE
  - TRUNCATE
  - DELETE FROM (without WHERE)
  
  # Kubernetes
  - kubectl delete
  - kubectl drain (without proper safeguards)
  - helm uninstall
  - helm delete
  
  # Cloud
  - aws ec2 terminate-instances
  - aws rds delete-db-instance
  - gcloud compute instances delete
  - az vm delete
  
  # Scaling to zero
  - scale --replicas=0
  - min-instances=0
```

## Email Notification System

### Configuration

```bash
# .env
EMAIL_ENABLED=true
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_SMTP_USER=devops-agent@yourcompany.com
EMAIL_SMTP_PASSWORD=your-app-password
EMAIL_FROM=devops-agent@yourcompany.com
EMAIL_TO=sre-team@yourcompany.com,devops-lead@yourcompany.com
EMAIL_CC=security-team@yourcompany.com
```

### Email Triggers

Emails are sent for:
1. **Dangerous operation detected** - Agent wants to do something potentially harmful
2. **Manual intervention required** - Issue cannot be auto-resolved safely
3. **Security alert** - Potential security issue detected
4. **Compliance violation** - Configuration doesn't meet standards
5. **Critical incident** - High-severity issue requiring attention
6. **Approval timeout** - Waiting for human approval
7. **Audit anomaly** - Unusual pattern detected

### Email Template

```
Subject: [DevOps Agent] Manual Intervention Required - <Incident Type>

Severity: CRITICAL/HIGH/MEDIUM
Incident ID: ABC-123
Time: 2026-06-12 11:30:00 UTC

SUMMARY:
The DevOps AI Agent has detected an issue that requires manual intervention.

ISSUE:
<Description of the problem>

AGENT RECOMMENDATION:
<What the agent suggests doing>

WHY MANUAL INTERVENTION IS REQUIRED:
<Explanation of why this is dangerous/requires human judgment>

SUGGESTED COMMANDS:
```bash
# Review the situation
kubectl get pods -n production

# If you decide to proceed, run:
kubectl delete pod problematic-pod -n production
```

CONTEXT:
- Namespace: production
- Resource: deployment/api-service
- Recent Changes: <list of recent changes>

LOGS:
<relevant log snippets>

TAKE ACTION:
1. Review the situation
2. Make informed decision
3. Execute commands manually if needed
4. Update runbook if this becomes common

DO NOT REPLY TO THIS EMAIL
View full incident: https://agent-dashboard.company.com/incidents/ABC-123
```

## DevSecOps Best Practices

### Security Scanning

The agent performs:
- ✅ Container image vulnerability scanning
- ✅ Secrets detection in code
- ✅ Configuration security checks
- ✅ Compliance validation
- ✅ Network policy validation
- ✅ RBAC permission auditing

### Security Alerts

```yaml
security_checks:
  - exposed_secrets
  - insecure_configurations
  - missing_network_policies
  - overly_permissive_rbac
  - unencrypted_secrets
  - outdated_dependencies
  - known_vulnerabilities
  - compliance_violations
```

### Compliance Frameworks

Supports checks for:
- CIS Benchmarks
- PCI-DSS
- SOC 2
- HIPAA
- GDPR
- ISO 27001

## Audit Trail

Every action is logged with:
```json
{
  "timestamp": "2026-06-12T11:30:00Z",
  "incident_id": "INC-123",
  "action_type": "notification_sent",
  "severity": "high",
  "reason": "Detected need for pod deletion",
  "recommended_action": "kubectl delete pod xyz",
  "why_blocked": "Deletion is a destructive operation",
  "notification_sent_to": ["email", "slack"],
  "human_intervention_required": true,
  "ai_reasoning": "Pod is in CrashLoopBackOff due to config error. Deleting would cause downtime. Recommended fix: update ConfigMap instead."
}
```

## Approval Workflow

### Multi-Level Approvals

```yaml
approval_levels:
  low_risk:
    - auto_approved: true
    - examples: ["restart pod", "scale up", "retry build"]
  
  medium_risk:
    - requires: ["lead_engineer"]
    - timeout: 30 minutes
    - examples: ["update config", "rollback deployment"]
  
  high_risk:
    - requires: ["sre_lead", "security_team"]
    - timeout: 1 hour
    - examples: ["modify firewall", "database migration"]
  
  critical_risk:
    - requires: ["cto", "security_officer"]
    - requires_video_call: true
    - examples: ["production database changes"]
  
  never_approved:
    - auto_blocked: true
    - examples: ["delete database", "terminate production"]
```

## Incident Severity Levels

```yaml
severity_levels:
  P0_CRITICAL:
    response: "Immediate notification + Page on-call"
    auto_remediation: false
    email: true
    sms: true
    phone_call: true
  
  P1_HIGH:
    response: "Email + Slack alert"
    auto_remediation: false
    email: true
    sms: false
  
  P2_MEDIUM:
    response: "Slack notification"
    auto_remediation: true (safe operations only)
    email: false
  
  P3_LOW:
    response: "Log only"
    auto_remediation: true
    email: false
```

## Security Incident Response

### Detected Security Issue

```
1. IMMEDIATELY:
   - Alert security team
   - Log all details
   - Isolate affected resources (if safe)
   - Preserve evidence

2. DO NOT:
   - Delete logs
   - Modify affected systems
   - Alert the attacker
   
3. NOTIFY:
   - security@company.com
   - SOC team
   - Incident commander
```

## Safe Rollback Strategy

### Before Rollback
1. ✅ Verify previous version exists
2. ✅ Check rollback is tested
3. ✅ Ensure data compatibility
4. ✅ Run dry-run simulation
5. ✅ Create backup of current state
6. ✅ Get approval

### Never Rollback
- ❌ Database schema changes (use migrations)
- ❌ Data deletions (irreversible)
- ❌ Security patches (unless breaking)
- ❌ To unknown/untagged versions

## Configuration Validation

Before applying any change:
```yaml
validation_checks:
  - syntax_valid: true
  - schema_valid: true
  - security_scan: passed
  - compliance_check: passed
  - dry_run_successful: true
  - peer_reviewed: true (for production)
  - tested_in_staging: true (for production)
```

## Emergency Stop

### Kill Switch
```bash
# Stop all agent operations immediately
curl -X POST https://agent.company.com/emergency-stop \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Or set environment variable
AGENT_EMERGENCY_STOP=true
```

### When to Use
- Rogue AI behavior detected
- Incorrect actions being taken
- Security breach suspected
- Human intervention needed

## Monitoring Agent Behavior

```yaml
agent_monitors:
  - failed_actions_per_hour: < 5
  - blocked_commands_per_day: monitored
  - approval_timeout_rate: < 10%
  - email_notification_rate: monitored
  - security_alerts: immediate escalation
```

## Summary

```
✅ SAFE: Read operations, diagnostics, reports
✅ SAFE: Restarts, scale UP, config updates (with approval)
⚠️  CAUTION: Rollbacks, scale DOWN (requires approval + email)
❌ BLOCKED: Deletions, terminations, formatting, data loss
📧 NOTIFY: All dangerous operations → Email + manual commands
```

---

**Remember: The agent is a helpful assistant, not a replacement for human judgment.**

For questions or to report unsafe behavior: security@yourcompany.com
