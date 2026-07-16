"""
Tests for DevOps AI Agent
Run: pytest tests/ -v
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tools.executor import SafeExecutor
from agent.prompts import get_system_prompt
from agent.classifier import classify_issue


# ─── Executor Safety Tests ────────────────────────────────────────────────────

class TestSafeExecutor:
    def setup_method(self):
        self.executor = SafeExecutor()

    def test_classifies_read_only_as_safe(self):
        assert self.executor._classify("kubectl get pods -n default") == "safe"
        assert self.executor._classify("kubectl describe pod my-pod") == "safe"
        assert self.executor._classify("kubectl logs my-pod") == "safe"
        assert self.executor._classify("df -h") == "safe"
        assert self.executor._classify("ps aux --sort=-%cpu") == "safe"

    def test_classifies_restart_as_allowed(self):
        assert self.executor._classify("kubectl rollout restart deployment/api") == "allowed"

    def test_classifies_scale_as_requires_approval_by_default(self):
        assert self.executor._classify("kubectl scale deployment/api --replicas=3") == "requires_approval"
        assert self.executor._classify("systemctl restart nginx") == "allowed"

    def test_classifies_delete_as_requires_approval(self):
        assert self.executor._classify("kubectl delete pod my-pod") == "requires_approval"
        assert self.executor._classify("rm -rf /var/log/app") == "requires_approval"
        assert self.executor._classify("kubectl exec -it my-pod -- bash") == "requires_approval"

    def test_blocks_dangerous_commands(self):
        assert self.executor._classify("dd if=/dev/zero of=/dev/sda") == "requires_approval"
        assert self.executor._classify("shutdown -r now") == "requires_approval"
        assert self.executor._classify("mkfs.ext4 /dev/sdb") == "requires_approval"

    @pytest.mark.asyncio
    async def test_blocks_unapproved_restart_when_auto_apply_false(self):
        self.executor.auto_apply = False
        result = await self.executor.run_safe("kubectl rollout restart deployment/api -n prod")
        assert result.get("blocked") is True
        assert result.get("requires_approval") is True

    @pytest.mark.asyncio
    async def test_allows_safe_commands_without_approval(self):
        with patch("asyncio.create_subprocess_shell") as mock_proc:
            mock_proc.return_value = AsyncMock(
                returncode=0,
                communicate=AsyncMock(return_value=(b"NAME   READY\npod-1   1/1", b"")),
            )
            result = await self.executor.run_safe("kubectl get pods")
            assert result.get("success") is True


# ─── Prompt Tests ─────────────────────────────────────────────────────────────

class TestPrompts:
    def test_returns_prompt_for_known_type(self):
        for t in ["cicd", "k8s", "server", "dockerfile"]:
            prompt = get_system_prompt(t)
            assert len(prompt) > 100
            assert isinstance(prompt, str)

    def test_returns_default_for_unknown_type(self):
        prompt = get_system_prompt("unknown_type")
        assert "DevOps" in prompt


# ─── Classifier Tests ─────────────────────────────────────────────────────────

class TestClassifier:
    def test_classifies_k8s_alerts(self):
        for name in ["PodCrashLooping", "ContainerOOMKilled", "ImagePullBackOff"]:
            assert classify_issue(name, {}) == "k8s"

    def test_classifies_server_alerts(self):
        for name in ["HighCPU", "DiskFull", "NginxDown", "HighMemoryUsage"]:
            assert classify_issue(name, {}) == "server"

    def test_classifies_cicd_alerts(self):
        for name in ["DeploymentFailed", "PipelineError", "BuildFailed"]:
            assert classify_issue(name, {}) == "cicd"


# ─── Integration: Agent with mocked Claude ────────────────────────────────────

class TestAgentLoop:
    @pytest.mark.asyncio
    async def test_agent_handles_k8s_incident(self):
        from agent.core import DevOpsAgent
        import os

        os.environ['ANTHROPIC_API_KEY'] = 'sk-ant-test-dummy-key-for-testing'

        with patch("anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client

            # Step 1: Claude requests tool
            tool_block = MagicMock()
            tool_block.type = "tool_use"
            tool_block.name = "get_k8s_context"
            tool_block.id = "tool_1"
            tool_block.input = {"namespace": "production"}

            mock_tool_response = MagicMock()
            mock_tool_response.stop_reason = "tool_use"
            mock_tool_response.content = [tool_block]

            # Step 2: Claude suggests non-destructive fix
            suggest_block = MagicMock()
            suggest_block.type = "tool_use"
            suggest_block.name = "suggest_fix"
            suggest_block.id = "tool_2"
            suggest_block.input = {
                "title": "Increase memory limits",
                "description": "Evidence: OOMKilled on api-pod",
                "commands": ["kubectl set resources deployment/api -n production --limits=memory=512Mi"],
                "verification_steps": ["kubectl get pods -n production"],
            }

            mock_suggest_response = MagicMock()
            mock_suggest_response.stop_reason = "tool_use"
            mock_suggest_response.content = [suggest_block]

            # Step 3: Claude concludes with evidence
            mock_end_response = MagicMock()
            mock_end_response.stop_reason = "end_turn"
            mock_end_response.content = [
                MagicMock(
                    type="text",
                    text="Evidence: get_k8s_context showed OOMKilled on api-pod.\nOOM detected. Suggested memory increase to 512Mi via suggest_fix.",
                )
            ]

            mock_client.messages.create.side_effect = [
                mock_tool_response, mock_suggest_response, mock_end_response,
            ]

            agent = DevOpsAgent()
            agent.k8s_collector.collect = AsyncMock(return_value={"pods": [{"name": "api-pod", "reason": "OOMKilled"}]})
            agent.notifier.send_resolution = AsyncMock()
            agent.notifier.send_fix_suggestion = AsyncMock()
            agent.incident_store = __import__("services.incident_store", fromlist=["IncidentStore"]).IncidentStore(
                __import__("storage.memory_storage", fromlist=["MemoryStorage"]).MemoryStorage()
            )
            agent.org_docs = __import__("services.org_docs", fromlist=["OrgDocs"]).OrgDocs(
                __import__("storage.memory_storage", fromlist=["MemoryStorage"]).MemoryStorage()
            )

            result = await agent.run({
                "type": "k8s",
                "namespace": "production",
                "pod": "api-pod",
                "org_id": "test-org",
            }, incident_id="INC-TEST-001", resume=False)

            assert result["resolved"] is True
            assert "OOM" in result["diagnosis"]
            assert result["grounding"]["grounded"] is True
            assert len(result["suggested_fixes"]) == 1
            assert result["suggestions_only"] is True
