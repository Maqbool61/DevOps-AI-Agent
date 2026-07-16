"""Tests for remote SSH command construction.

These tests inspect the SSH argv built by collectors/server.py and
tools/executor.py without opening real SSH connections.
"""

import pytest
from unittest.mock import AsyncMock, patch


def _argv_contains(calls, needle):
    """Return True if any positional arg in any call contains needle."""
    for call in calls:
        for arg in call.args:
            if needle in arg:
                return True
    return False


@pytest.fixture
def mock_async_subprocess():
    proc = AsyncMock()
    proc.communicate.return_value = (b"ok", b"")
    proc.returncode = 0
    with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
        yield mock_exec


@pytest.fixture
def mock_async_shell():
    proc = AsyncMock()
    proc.communicate.return_value = (b"ok", b"")
    proc.returncode = 0
    with patch("asyncio.create_subprocess_shell", return_value=proc):
        yield


class TestServerCollectorSSH:
    @pytest.mark.asyncio
    async def test_no_strict_host_key_checking(
        self, mock_async_subprocess, mock_async_shell
    ):
        from collectors.server import ServerCollector

        collector = ServerCollector()
        await collector.collect(host="10.0.0.1")

        assert not _argv_contains(
            mock_async_subprocess.call_args_list, "StrictHostKeyChecking=no"
        )

    @pytest.mark.asyncio
    async def test_known_hosts_option(
        self, monkeypatch, mock_async_subprocess, mock_async_shell
    ):
        from collectors.server import ServerCollector

        monkeypatch.setenv("SSH_KNOWN_HOSTS", "/etc/agent/known_hosts")
        collector = ServerCollector()
        await collector.collect(host="10.0.0.1")

        assert _argv_contains(
            mock_async_subprocess.call_args_list,
            "UserKnownHostsFile=/etc/agent/known_hosts",
        )

    @pytest.mark.asyncio
    async def test_remote_user_format(
        self, monkeypatch, mock_async_subprocess, mock_async_shell
    ):
        from collectors.server import ServerCollector

        monkeypatch.setenv("SSH_REMOTE_USER", "ubuntu")
        collector = ServerCollector()
        await collector.collect(host="10.0.0.1")

        assert _argv_contains(mock_async_subprocess.call_args_list, "ubuntu@10.0.0.1")

    @pytest.mark.asyncio
    async def test_host_with_user_unchanged(
        self, monkeypatch, mock_async_subprocess, mock_async_shell
    ):
        from collectors.server import ServerCollector

        monkeypatch.setenv("SSH_REMOTE_USER", "ubuntu")
        collector = ServerCollector()
        await collector.collect(host="centos@10.0.0.1")

        assert _argv_contains(mock_async_subprocess.call_args_list, "centos@10.0.0.1")
        assert not _argv_contains(
            mock_async_subprocess.call_args_list, "ubuntu@10.0.0.1"
        )


class TestSafeExecutorSSH:
    @pytest.mark.asyncio
    async def test_no_strict_host_key_checking(self, mock_async_subprocess):
        from tools.executor import SafeExecutor

        executor = SafeExecutor()
        await executor.run("docker ps", host="10.0.0.1")

        args = mock_async_subprocess.call_args.args
        assert not any("StrictHostKeyChecking=no" in arg for arg in args)

    @pytest.mark.asyncio
    async def test_known_hosts_option(self, monkeypatch, mock_async_subprocess):
        from tools.executor import SafeExecutor

        monkeypatch.setenv("SSH_KNOWN_HOSTS", "/etc/agent/known_hosts")
        executor = SafeExecutor()
        await executor.run("docker ps", host="10.0.0.1")

        args = mock_async_subprocess.call_args.args
        assert any("UserKnownHostsFile=/etc/agent/known_hosts" in arg for arg in args)

    @pytest.mark.asyncio
    async def test_remote_user_format(self, monkeypatch, mock_async_subprocess):
        from tools.executor import SafeExecutor

        monkeypatch.setenv("SSH_REMOTE_USER", "ubuntu")
        executor = SafeExecutor()
        await executor.run("docker ps", host="10.0.0.1")

        args = mock_async_subprocess.call_args.args
        assert any("ubuntu@10.0.0.1" in arg for arg in args)

    @pytest.mark.asyncio
    async def test_host_with_user_unchanged(self, monkeypatch, mock_async_subprocess):
        from tools.executor import SafeExecutor

        monkeypatch.setenv("SSH_REMOTE_USER", "ubuntu")
        executor = SafeExecutor()
        await executor.run("docker ps", host="centos@10.0.0.1")

        args = mock_async_subprocess.call_args.args
        assert any("centos@10.0.0.1" in arg for arg in args)
        assert not any("ubuntu@10.0.0.1" in arg for arg in args)
