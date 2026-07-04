"""Tests for non-destructive fix suggestions."""
from tools.fix_suggestions import is_non_destructive, validate_suggestion


class TestFixSuggestions:
    def test_allows_safe_commands(self):
        ok, _ = is_non_destructive("docker restart broken-app")
        assert ok
        ok, _ = is_non_destructive("systemctl reload nginx")
        assert ok
        ok, _ = is_non_destructive("kubectl rollout restart deployment/api -n prod")
        assert ok

    def test_blocks_destructive_commands(self):
        ok, reason = is_non_destructive("kubectl delete pod api-xyz -n prod")
        assert not ok
        ok, _ = is_non_destructive("rm -rf /var/log")
        assert not ok
        ok, _ = is_non_destructive("DROP TABLE users")
        assert not ok

    def test_validate_records_safe_suggestion(self):
        result = validate_suggestion(
            "Fix missing env var",
            "Container exits because REQUIRED_ENV is unset",
            ["docker compose -f /opt/app/docker-compose.yml up -d"],
            config_snippets=["environment:\n  REQUIRED_ENV: ok"],
        )
        assert result["recorded"] is True
        assert len(result["commands"]) == 1

    def test_validate_rejects_all_destructive(self):
        result = validate_suggestion(
            "Bad fix",
            "Should not record",
            ["rm -rf /", "kubectl delete deployment api"],
        )
        assert result["recorded"] is False
