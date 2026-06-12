"""
Slack Notifier
Sends rich incident summaries and interactive approval buttons to Slack.
"""
import os
from typing import Optional

import httpx
import structlog

log = structlog.get_logger()

SEVERITY_EMOJI = {
    "info": "ℹ️",
    "warning": "⚠️",
    "critical": "🔴",
}


class SlackNotifier:
    def __init__(self):
        self.webhook_url = os.getenv("SLACK_WEBHOOK_URL", "")
        self.approval_channel = os.getenv("SLACK_APPROVAL_CHANNEL", "#devops")
        self.bot_token = os.getenv("SLACK_BOT_TOKEN", "")

    async def send_message(
        self,
        message: str,
        severity: str = "info",
        resolved: bool = False,
        requires_approval: bool = False,
        approval_command: Optional[str] = None,
    ):
        if not self.webhook_url:
            log.warning("SLACK_WEBHOOK_URL not set — skipping notification")
            return

        emoji = "✅" if resolved else SEVERITY_EMOJI.get(severity, "ℹ️")
        status_text = "RESOLVED" if resolved else severity.upper()

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} DevOps AI Agent — {status_text}",
                },
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": message},
            },
        ]

        if requires_approval and approval_command:
            import base64
            encoded = base64.b64encode(approval_command.encode()).decode()
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✅ Approve & Execute"},
                        "style": "primary",
                        "action_id": "approve_action",
                        "value": f"PENDING:{encoded}",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "❌ Reject"},
                        "style": "danger",
                        "action_id": "reject_action",
                        "value": "reject",
                    },
                ],
            })
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Pending command:*\n```{approval_command}```",
                },
            })

        payload = {"blocks": blocks}

        async with httpx.AsyncClient(timeout=10) as client:
            try:
                await client.post(self.webhook_url, json=payload)
            except Exception as e:
                log.error("Slack notification failed", error=str(e))

    async def send_approval_request(self, description: str, command: str, encoded: str):
        await self.send_message(
            f"*Action requires approval:*\n{description}\n\n```{command}```",
            severity="warning",
            requires_approval=True,
            approval_command=command,
        )

    async def send_resolution(self, incident_id: str, result: dict):
        resolved = result.get("resolved", False)
        actions = result.get("actions", [])
        diagnosis = result.get("diagnosis", "")

        action_summary = ""
        if actions:
            successful = [a for a in actions if not a.get("result", {}).get("error")]
            action_summary = f"\n*Actions taken ({len(successful)}/{len(actions)} successful):*\n"
            for a in actions[:5]:
                tool = a.get("tool", "")
                res = a.get("result", {})
                ok = "✅" if not res.get("error") else "❌"
                action_summary += f"{ok} `{tool}`\n"

        message = (
            f"*Incident:* `{incident_id}`\n"
            f"*Status:* {'✅ Resolved' if resolved else '⚠️ Needs attention'}\n\n"
            f"{diagnosis[:800]}"
            f"{action_summary}"
        )

        await self.send_message(
            message,
            severity="info" if resolved else "warning",
            resolved=resolved,
        )

    async def send_error(self, incident_id: str, error: str):
        await self.send_message(
            f"*Agent error for incident `{incident_id}`:*\n```{error}```\n\nEscalating to on-call.",
            severity="critical",
        )
