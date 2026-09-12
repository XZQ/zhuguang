"""Bounded runtime sweeps, runnable independently of the HTTP/model workers."""

from __future__ import annotations

import logging
import os
import threading
import time

LOGGER = logging.getLogger(__name__)


class RecoveryScheduler:
    def __init__(self, runtime, *, interval=5.0):
        if not 0 < interval <= 30:
            raise ValueError("Recovery scan interval must be in (0, 30] seconds")
        self.runtime = runtime
        self.interval = interval
        self.stop_event = threading.Event()
        self.thread = None
        self.last_success = None
        self.failures = 0
        self.scan_seconds = 0.0
        self.scanned = 0

    def healthy(self):
        return (
            self.last_success is not None
            and (time.monotonic() - self.last_success <= max(15, 3 * self.interval))
            and not self.stop_event.is_set()
        )

    def sweep(self):
        started = time.monotonic()
        try:
            self.scanned = self.runtime.recovery.tick()
        except Exception:
            self.failures += 1
            self.last_success = None
            # Avoid exception payloads that may contain connection credentials.
            LOGGER.error("Runtime recovery scan failed; inspect database and scoped configuration")
            return False
        self.scan_seconds = time.monotonic() - started
        self.last_success = time.monotonic()
        return True

    def _run(self):
        while not self.stop_event.is_set():
            self.sweep()
            self.stop_event.wait(self.interval)

    def start(self):
        if self.thread is not None:
            raise RuntimeError("Recovery scheduler already started")
        self.thread = threading.Thread(target=self._run, name="runtime-recovery", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)

    def metrics(self):
        age = time.monotonic() - self.last_success if self.last_success else -1
        return (
            f"dianxun_recovery_healthy {int(self.healthy())}\n"
            f"dianxun_recovery_scan_age_seconds {age}\n"
            f"dianxun_recovery_scan_duration_seconds {self.scan_seconds}\n"
            f"dianxun_recovery_scan_failures_total {self.failures}\n"
            f"dianxun_recovery_contexts_scanned {self.scanned}\n"
        ) + "".join(
            f"dianxun_recovery_{key} {value}\n"
            for key, value in self.runtime.recovery.metric_snapshot.items()
        )


def main():
    from .mcp.p0 import default_service
    from .runtime import RuntimeService, load_principals

    principals = load_principals(os.environ.get("DIANXUN_RUNTIME_TOKENS_JSON", "{}"))
    if not principals:
        raise ValueError("Recovery scheduler requires explicit runtime scopes")
    runtime = RuntimeService(default_service(), principals.values())
    scheduler = RecoveryScheduler(runtime)
    try:
        scheduler._run()
    except KeyboardInterrupt:
        scheduler.stop()


if __name__ == "__main__":
    main()
