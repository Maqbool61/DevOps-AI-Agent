"""
DevOps AI Agent — FastAPI Webhook Server
Receives events from GitHub, Alertmanager, and manual triggers.
"""
import asyncio
import hashlib
import hmac
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

import structlog
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from agent.core import DevOpsAgent
from tools.notify import SlackNotifier

load_dotenv()

log = structlog.get_logger()

# Shared agent instance
agent = DevOpsAgent()
notifier = SlackNotifier()

# In-memory audit log (replace with DB in production)
audit_log: list[dict] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("DevOps AI Agent starting", auto_apply=os.getenv("AUTO_APPLY", "false"))
    yield
    log.info("DevOps AI Agent shutting down")


app = FastAPI(
    title="DevOps AI Agent",
    description="Autonomous incident diagnosis and remediation powered by Claude",
    version="1.0.0",
    lifespan=lifespan,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def verify_github_signature(payload: bytes, signature: str) -> bool:
    secret = os.getenv("WEBHOOK_SECRET", "").encode()
    expected = "sha256=" + hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def handle_incident(context: dict):
    """Core handler: collect → analyze → act → audit."""
    incident_id = f"INC-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    log.info("Handling incident", id=incident_id, type=context.get("type"))

    try:
        result = await agent.run(context)

        entry = {
            "id": incident_id,
            "timestamp": datetime.utcnow().isoformat(),
            "incident": context,
            "diagnosis": result.get("diagnosis"),
            "actions_taken": result.get("actions", []),
            "resolved": result.get("resolved", False),
            "ai_reasoning": result.get("reasoning"),
        }
        audit_log.append(entry)

        await notifier.send_resolution(incident_id, result)
        log.info("Incident handled", id=incident_id, resolved=result.get("resolved"))

    except Exception as e:
        log.error("Incident handling failed", id=incident_id, error=str(e))
        await notifier.send_error(incident_id, str(e))


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "auto_apply": os.getenv("AUTO_APPLY", "false")}


@app.get("/audit")
async def get_audit(limit: int = 50):
    """Return recent incident audit log."""
    return {"events": audit_log[-limit:], "total": len(audit_log)}


@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(None),
    x_hub_signature_256: str = Header(None),
):
    """Receive GitHub Actions failure webhooks."""
    body = await request.body()

    # Verify signature
    if os.getenv("WEBHOOK_SECRET"):
        if not x_hub_signature_256 or not verify_github_signature(body, x_hub_signature_256):
            raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()

    if x_github_event == "workflow_run":
        run = payload.get("workflow_run", {})
        if run.get("conclusion") == "failure":
            context = {
                "type": "cicd",
                "source": "github_actions",
                "repo": payload.get("repository", {}).get("full_name"),
                "run_id": run.get("id"),
                "workflow_name": run.get("name"),
                "branch": run.get("head_branch"),
                "commit": run.get("head_sha", "")[:8],
                "html_url": run.get("html_url"),
            }
            background_tasks.add_task(handle_incident, context)
            return {"status": "processing", "type": "cicd"}

    return {"status": "ignored", "event": x_github_event}


@app.post("/webhook/alertmanager")
async def alertmanager_webhook(request: Request, background_tasks: BackgroundTasks):
    """Receive Prometheus Alertmanager webhooks."""
    payload = await request.json()

    for alert in payload.get("alerts", []):
        if alert.get("status") != "firing":
            continue

        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        alertname = labels.get("alertname", "")

        # Classify alert type
        issue_type = _classify_alert(alertname, labels)

        context = {
            "type": issue_type,
            "source": "alertmanager",
            "alertname": alertname,
            "severity": labels.get("severity", "warning"),
            "namespace": labels.get("namespace"),
            "pod": labels.get("pod"),
            "service": labels.get("service"),
            "node": labels.get("node"),
            "summary": annotations.get("summary", ""),
            "description": annotations.get("description", ""),
            "labels": labels,
        }
        background_tasks.add_task(handle_incident, context)

    return {"status": "processing", "alerts": len(payload.get("alerts", []))}


@app.post("/webhook/manual")
async def manual_trigger(request: Request, background_tasks: BackgroundTasks):
    """
    Manually trigger the agent with arbitrary context.

    Body:
    {
        "type": "k8s|cicd|server|dockerfile",
        "description": "Pod api-xyz is CrashLoopBackOff in prod namespace",
        "namespace": "production",   // optional
        "pod": "api-xyz-abc",        // optional
        "raw_logs": "..."            // optional
    }
    """
    context = await request.json()
    if "type" not in context:
        raise HTTPException(status_code=400, detail="'type' field required")

    context["source"] = "manual"
    background_tasks.add_task(handle_incident, context)
    return {"status": "processing", "context": context}


@app.post("/slack/action")
async def slack_action(request: Request, background_tasks: BackgroundTasks):
    """Handle Slack interactive button approvals."""
    form = await request.form()
    payload = __import__("json").loads(form.get("payload", "{}"))

    action = payload.get("actions", [{}])[0]
    action_id = action.get("action_id", "")
    value = action.get("value", "")

    if action_id == "approve_action":
        incident_id, encoded_cmd = value.split(":", 1)
        import base64
        cmd = base64.b64decode(encoded_cmd).decode()
        background_tasks.add_task(agent.execute_approved_action, incident_id, cmd)
        return JSONResponse({"text": f"✅ Approved. Executing: `{cmd}`"})

    elif action_id == "reject_action":
        return JSONResponse({"text": "❌ Action rejected. Incident escalated to on-call."})

    return JSONResponse({"text": "Unknown action"})


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _classify_alert(alertname: str, labels: dict) -> str:
    alertname_lower = alertname.lower()
    if any(k in alertname_lower for k in ["pod", "container", "crash", "oom", "image"]):
        return "k8s"
    if any(k in alertname_lower for k in ["cpu", "memory", "disk", "load", "nginx", "service"]):
        return "server"
    if any(k in alertname_lower for k in ["deploy", "pipeline", "build", "ci"]):
        return "cicd"
    return "server"
