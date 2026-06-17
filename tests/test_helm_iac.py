"""Tests for Helm and IaC tools."""
import pytest

from tools.helm_tools import HelmTools
from tools.iac_tools import IaCTools


class TestHelmTools:
    def setup_method(self):
        self.tools = HelmTools()

    def test_blocks_uninstall_in_rollback_path(self):
        reason = self.tools._is_blocked("helm uninstall my-release -n prod")
        assert reason is not None

    def test_allows_rollback_command_pattern(self):
        reason = self.tools._is_blocked("helm rollback api 3 -n staging")
        assert reason is None

    def test_namespace_gate(self):
        blocked = self.tools._check_namespace("forbidden-ns")
        assert blocked is not None
        assert blocked.get("blocked") is True


class TestIaCTools:
    def setup_method(self):
        self.tools = IaCTools()

    def test_blocks_apply_subcommand(self):
        blocked = self.tools._validate_subcommand("apply")
        assert blocked is not None
        assert blocked.get("blocked") is True

    def test_allows_plan(self):
        blocked = self.tools._validate_subcommand("plan", "-input=false")
        assert blocked is None

    def test_allows_validate(self):
        blocked = self.tools._validate_subcommand("validate")
        assert blocked is None

    @pytest.mark.asyncio
    async def test_missing_workspace_returns_error(self):
        self.tools.default_workspace = ""
        result = await self.tools.terraform_plan(None)
        assert "error" in result
