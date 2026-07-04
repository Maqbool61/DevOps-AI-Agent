"""Tests for escalation detection and ticketing."""
from datetime import datetime, timedelta, timezone

from collectors.database_policy import is_database_incident, incident_involves_blocked_database
from services.escalation import EscalationService, parse_queue_timestamp


class TestDatabaseIncidentDetection:
    def test_detects_rds_alert(self):
        assert is_database_incident({"alertname": "RDSHighCPU", "type": "cloud_aws"})

    def test_detects_resource_type(self):
        assert is_database_incident({"type": "cloud_aws", "resource_type": "rds"})

    def test_non_db_incident(self):
        assert not is_database_incident({"type": "k8s", "alertname": "PodCrashLooping"})

    def test_blocked_db_tool(self):
        actions = [{"tool": "get_cloud_resource", "result": {"blocked": True, "error": "Database collection is disabled"}}]
        assert incident_involves_blocked_database(actions)


class TestEscalationEvaluate:
    def setup_method(self):
        self.svc = EscalationService()
        self.svc.enabled = True
        self.svc.timeout_minutes = 10
        self.started = datetime.now(timezone.utc) - timedelta(minutes=12)

    def test_escalates_timeout_unresolved(self):
        decision = self.svc.evaluate(
            "INC-1", "acme", {"type": "k8s"},
            {"resolved": False, "actions": [], "diagnosis": "Still investigating"},
            self.started,
        )
        assert decision.should_escalate
        assert "timeout_unresolved" in decision.reasons
        assert "unresolved" in decision.reasons

    def test_escalates_database_issue(self):
        decision = self.svc.evaluate(
            "INC-2", "acme",
            {"type": "cloud_aws", "resource_type": "rds", "resource_id": "db-1"},
            {"resolved": False, "actions": []},
            datetime.now(timezone.utc),
        )
        assert decision.should_escalate
        assert "database_issue" in decision.reasons

    def test_escalates_agent_error(self):
        decision = self.svc.evaluate(
            "INC-3", "acme", {"type": "k8s"}, None,
            datetime.now(timezone.utc), error="API timeout",
        )
        assert decision.should_escalate
        assert "agent_error" in decision.reasons

    def test_no_escalation_when_resolved_quickly(self):
        decision = self.svc.evaluate(
            "INC-4", "acme", {"type": "k8s"},
            {"resolved": True, "grounding": {"grounded": True}, "actions": [{"tool": "get_k8s_context", "result": {}}]},
            datetime.now(timezone.utc),
        )
        assert not decision.should_escalate

    def test_escalates_not_grounded(self):
        decision = self.svc.evaluate(
            "INC-5", "acme", {"type": "k8s"},
            {"resolved": False, "grounding": {"grounded": False}, "actions": []},
            datetime.now(timezone.utc),
        )
        assert decision.should_escalate
        assert "not_grounded" in decision.reasons


class TestQueueTimestamp:
    def test_parse_created_at(self):
        entry = {"created_at": "2026-06-17T12:00:00+00:00"}
        ts = parse_queue_timestamp(entry)
        assert ts.year == 2026
