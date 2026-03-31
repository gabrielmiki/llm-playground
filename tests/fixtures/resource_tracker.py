"""Resource tracking fixtures for connection and socket verification."""

from __future__ import annotations

import asyncio
import platform
import subprocess
from dataclasses import dataclass
from typing import Any

import pytest


@dataclass
class ConnectionStats:
    """Statistics about network connections."""

    total_connections: int = 0
    time_wait_count: int = 0
    established_count: int = 0
    listen_count: int = 0
    snapshot_time: float = 0.0


class SocketInspector:
    """Cross-platform socket state inspector.

    Uses platform-specific commands to inspect connection states:
    - Linux: /proc/net/tcp or ss command
    - macOS: lsof command
    - Windows: netstat command
    """

    def __init__(self, port: int | None = None) -> None:
        self.port = port
        self._system = platform.system()

    def _linux_snapshot(self) -> ConnectionStats:
        """Snapshot connections on Linux using ss."""
        stats = ConnectionStats()
        try:
            cmd = ["ss", "-tan", "state", "established", "time-wait", "listen"]
            if self.port:
                cmd.extend(["sport", f":{self.port}"])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            lines = result.stdout.strip().split("\n")[1:]
            for line in lines:
                line_lower = line.lower()
                if "time-wait" in line_lower:
                    stats.time_wait_count += 1
                elif "listen" in line_lower:
                    stats.listen_count += 1
                else:
                    stats.established_count += 1
                stats.total_connections += 1
        except subprocess.TimeoutExpired, FileNotFoundError:
            pass
        return stats

    def _macos_snapshot(self) -> ConnectionStats:
        """Snapshot connections on macOS using lsof."""
        stats = ConnectionStats()
        try:
            cmd = ["lsof", "-i", "-n", "-P"]
            if self.port:
                cmd.extend(["-i", f":{self.port}"])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            lines = result.stdout.strip().split("\n")[1:]
            for line in lines:
                line_lower = line.lower()
                if "time_wait" in line_lower or "time-wait" in line_lower:
                    stats.time_wait_count += 1
                elif "listen" in line_lower:
                    stats.listen_count += 1
                elif "established" in line_lower:
                    stats.established_count += 1
                stats.total_connections += 1
        except subprocess.TimeoutExpired, FileNotFoundError:
            pass
        return stats

    def snapshot(self) -> ConnectionStats:
        """Take a snapshot of current connection states."""
        import time

        stats = ConnectionStats()
        if self._system == "Linux":
            stats = self._linux_snapshot()
        elif self._system == "Darwin":
            stats = self._macos_snapshot()
        stats.snapshot_time = time.time()
        return stats


class ResourceTracker:
    """Tracks resource usage during async operations.

    Provides before/after snapshots to verify cleanup.
    """

    def __init__(self, port: int | None = None) -> None:
        self.inspector = SocketInspector(port)
        self.before: ConnectionStats | None = None
        self.after: ConnectionStats | None = None

    async def track(self, coro: Any) -> Any:
        """Execute coroutine while tracking resource usage."""
        self.before = self.inspector.snapshot()
        try:
            result = await coro
            return result
        finally:
            await asyncio.sleep(0.1)
            self.after = self.inspector.snapshot()

    def assert_clean(self) -> None:
        """Assert that connections returned to baseline."""
        if self.before is None or self.after is None:
            pytest.fail("Must call track() before assert_clean()")

        assert self.after.established_count <= self.before.established_count, (
            f"Connection leak: {self.after.established_count} > {self.before.established_count}"
        )
        assert self.after.time_wait_count <= self.before.time_wait_count + 1, (
            f"TIME_WAIT leak: {self.after.time_wait_count} > {self.before.time_wait_count}"
        )


@pytest.fixture
def socket_inspector() -> SocketInspector:
    """Provide a socket inspector for the current platform."""
    return SocketInspector()


@pytest.fixture
def resource_tracker() -> ResourceTracker:
    """Provide a resource tracker for connection cleanup verification."""
    return ResourceTracker()


@pytest.fixture
def resource_tracker_with_port(resource_tracker: ResourceTracker) -> ResourceTracker:
    """Provide a resource tracker scoped to a specific port."""
    return ResourceTracker(port=8080)
