# Postman Collection

Import these files into [Postman](https://www.postman.com/) to test the DevOps AI Agent API.

## Files

| File | Purpose |
|------|---------|
| `DevOps-AI-Agent.postman_collection.json` | All API endpoints with test scripts |
| `DevOps-AI-Agent-Local.postman_environment.json` | Local dev variables (`baseUrl`, `orgId`) |

## Quick start

1. Start the agent: `uvicorn api.server:app --reload --port 8000`
2. Postman → **Import** → select both JSON files
3. Select environment **DevOps AI Agent — Local** (top-right)
4. Run **End-to-End Test Flow** folder in order

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `baseUrl` | `http://localhost:8000` | Agent base URL |
| `orgId` | `acme-corp` | Organization ID for scoped storage |
| `docPath` | `runbooks/k8s-oom.md` | Path for file upload tests |
| `incidentId` | *(auto)* | Set by webhook test scripts |

## Collection structure

```
DevOps AI Agent API
├── Health & Audit
│   ├── Health Check
│   └── Get Audit Log
├── Organization Documentation
│   ├── Upload Doc (JSON)
│   ├── Upload Doc (File)
│   ├── List Docs
│   ├── Get Doc
│   └── Delete Doc
├── Webhooks
│   ├── Manual Trigger — K8s / CI/CD / Server / ArgoCD
│   ├── Alertmanager Webhook
│   └── GitHub Actions Webhook
├── Slack Integration
│   ├── Approve / Reject
└── End-to-End Test Flow
    ├── 1. Health Check
    ├── 2. Upload Runbook
    ├── 3. Trigger K8s Incident
    └── 4. Poll Audit
```

## Documentation

- [API Reference](../docs/API_REFERENCE.md)
- [API Testing Guide](../docs/API_TESTING.md)

## Production environment

Duplicate the environment and update:

```
baseUrl = https://agent.yourcompany.com
orgId   = your-production-org
```
