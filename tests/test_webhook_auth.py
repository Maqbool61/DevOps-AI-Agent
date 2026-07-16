"""
Tests for webhook authentication on /webhook/alertmanager and /webhook/manual.

Mirrors the GitHub endpoint behaviour: HMAC-SHA256 over the raw request body,
header `X-Hub-Signature-256`, secret `WEBHOOK_SECRET`, verification skipped when
no secret is configured.
"""

import hashlib
import hmac
import json
import os

# DevOpsAgent is instantiated at import time and requires a key.
os.environ.setdefault("ANTHROPIC_API_KEY", "dummy-test-key")

import pytest
from fastapi.testclient import TestClient

from api.server import app

SECRET = "test-webhook-secret"

ALERTMANAGER_PAYLOAD = {
    "alerts": [
        {
            "status": "firing",
            "labels": {"alertname": "PodCrashLooping", "namespace": "default"},
            "annotations": {"summary": "Pod is crash looping"},
        }
    ]
}

MANUAL_PAYLOAD = {
    "type": "k8s",
    "namespace": "default",
    "pod": "test-pod",
    "description": "Test incident",
}

GITHUB_PAYLOAD = {
    "action": "completed",
    "workflow_run": {
        "conclusion": "failure",
        "id": 12345,
        "name": "CI",
        "head_branch": "main",
        "head_sha": "abc123def456",
        "html_url": "https://github.com/org/repo/actions/runs/12345",
    },
    "repository": {"full_name": "org/repo"},
}


def _sign(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET", SECRET)
    return TestClient(app)


@pytest.fixture
def no_secret_client(monkeypatch):
    monkeypatch.delenv("WEBHOOK_SECRET", raising=False)
    return TestClient(app)


class TestAlertmanagerWebhookAuth:
    def test_valid_signature_accepted(self, client):
        body = json.dumps(ALERTMANAGER_PAYLOAD).encode()
        response = client.post(
            "/webhook/alertmanager",
            headers={"X-Hub-Signature-256": _sign(body)},
            content=body,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "queued"

    def test_invalid_signature_rejected(self, client):
        body = json.dumps(ALERTMANAGER_PAYLOAD).encode()
        response = client.post(
            "/webhook/alertmanager",
            headers={"X-Hub-Signature-256": "sha256=invalid"},
            content=body,
        )
        assert response.status_code == 401

    def test_missing_signature_rejected(self, client):
        body = json.dumps(ALERTMANAGER_PAYLOAD).encode()
        response = client.post("/webhook/alertmanager", content=body)
        assert response.status_code == 401

    def test_signature_for_different_body_rejected(self, client):
        real_body = json.dumps(ALERTMANAGER_PAYLOAD).encode()
        other_body = json.dumps({"alerts": []}).encode()
        response = client.post(
            "/webhook/alertmanager",
            headers={"X-Hub-Signature-256": _sign(other_body)},
            content=real_body,
        )
        assert response.status_code == 401

    def test_no_secret_skips_verification(self, no_secret_client):
        body = json.dumps(ALERTMANAGER_PAYLOAD).encode()
        response = no_secret_client.post("/webhook/alertmanager", content=body)
        assert response.status_code == 200
        assert response.json()["status"] == "queued"


class TestManualWebhookAuth:
    def test_valid_signature_accepted(self, client):
        body = json.dumps(MANUAL_PAYLOAD).encode()
        response = client.post(
            "/webhook/manual",
            headers={"X-Hub-Signature-256": _sign(body)},
            content=body,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "queued"

    def test_invalid_signature_rejected(self, client):
        body = json.dumps(MANUAL_PAYLOAD).encode()
        response = client.post(
            "/webhook/manual",
            headers={"X-Hub-Signature-256": "sha256=invalid"},
            content=body,
        )
        assert response.status_code == 401

    def test_missing_signature_rejected(self, client):
        body = json.dumps(MANUAL_PAYLOAD).encode()
        response = client.post("/webhook/manual", content=body)
        assert response.status_code == 401

    def test_signature_for_different_body_rejected(self, client):
        real_body = json.dumps(MANUAL_PAYLOAD).encode()
        other_body = json.dumps({"type": "k8s"}).encode()
        response = client.post(
            "/webhook/manual",
            headers={"X-Hub-Signature-256": _sign(other_body)},
            content=real_body,
        )
        assert response.status_code == 401

    def test_no_secret_skips_verification(self, no_secret_client):
        body = json.dumps(MANUAL_PAYLOAD).encode()
        response = no_secret_client.post("/webhook/manual", content=body)
        assert response.status_code == 200
        assert response.json()["status"] == "queued"


class TestGitHubWebhookRegression:
    """Ensure the existing GitHub webhook auth path still works."""

    def test_valid_signature_accepted(self, client):
        body = json.dumps(GITHUB_PAYLOAD).encode()
        response = client.post(
            "/webhook/github",
            headers={
                "X-GitHub-Event": "workflow_run",
                "X-Hub-Signature-256": _sign(body),
            },
            content=body,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "queued"

    def test_invalid_signature_rejected(self, client):
        body = json.dumps(GITHUB_PAYLOAD).encode()
        response = client.post(
            "/webhook/github",
            headers={
                "X-GitHub-Event": "workflow_run",
                "X-Hub-Signature-256": "sha256=invalid",
            },
            content=body,
        )
        assert response.status_code == 401

    def test_no_secret_skips_verification(self, no_secret_client):
        body = json.dumps(GITHUB_PAYLOAD).encode()
        response = no_secret_client.post(
            "/webhook/github",
            headers={"X-GitHub-Event": "workflow_run"},
            content=body,
        )
        assert response.status_code == 200
