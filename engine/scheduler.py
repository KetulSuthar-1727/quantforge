"""Explicit, fail-closed scheduling for the historical strategy scanner.

The scheduler never starts on import. Call ``start`` explicitly or drive
``run_due`` with a supplied datetime in tests and embedded applications.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path
import sqlite3
import threading
import time

from engine.us_market_calendar import USMarketCalendar

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SchedulerConfig:
    interval_seconds: int = 300
    session_only: bool = True
    allow_pre_market: bool = False
    allow_after_hours: bool = False
    retry_attempts: int = 1
    retry_delay_seconds: float = 2.0

    def __post_init__(self):
        if self.interval_seconds < 1 or self.retry_attempts < 1 or self.retry_delay_seconds < 0:
            raise ValueError("Scheduler intervals and retry settings are invalid.")
        if self.allow_pre_market or self.allow_after_hours:
            raise ValueError("Extended sessions are not supported; regular session only.")


class SchedulerStore:
    """Durable run history and last-known status; no trading state is stored here."""
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS scheduler_runs (
                id INTEGER PRIMARY KEY, started_at TEXT NOT NULL, ended_at TEXT NOT NULL,
                outcome TEXT NOT NULL, duration_seconds REAL NOT NULL,
                error TEXT, result_summary TEXT)""")

    def _connect(self):
        return sqlite3.connect(self.path, timeout=5)

    def record(self, started, ended, outcome, duration, error=None, summary=None):
        import json
        with self._connect() as db:
            db.execute("INSERT INTO scheduler_runs(started_at,ended_at,outcome,duration_seconds,error,result_summary) VALUES(?,?,?,?,?,?)",
                       (started.isoformat(), ended.isoformat(), outcome, duration, error,
                        json.dumps(summary, sort_keys=True) if summary is not None else None))

    def last_run(self):
        with self._connect() as db:
            return db.execute("SELECT started_at,ended_at,outcome,duration_seconds,error,result_summary FROM scheduler_runs ORDER BY id DESC LIMIT 1").fetchone()


class ScanScheduler:
    """Runs a supplied scanner without overlap; scheduler ticks never trade."""
    def __init__(self, scanner, *, config=None, calendar=None, store=None,
                 clock=None, sleep=None):
        if not callable(getattr(scanner, "scan", None)):
            raise TypeError("scanner must provide scan().")
        self.scanner = scanner
        self.config = config or SchedulerConfig()
        self.calendar = calendar or USMarketCalendar()
        self.store = store
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.sleep = sleep or time.sleep
        self._lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._running = False
        self._last_run = None
        self._last_outcome = None
        self._last_error = None
        self._consecutive_failures = 0
        self._next_run = None
        self._blocked_reason = None
        self._status = "stopped"
        # Recovery is safe for scan history only. No automatic trading resumes.
        if store is not None:
            try:
                row = store.last_run()
                if row:
                    self._last_run = {"started_at": row[0], "ended_at": row[1],
                                      "outcome": row[2], "duration_seconds": row[3],
                                      "error": row[4]}
                    self._last_outcome = row[2]
                    self._consecutive_failures = 0 if row[2] == "success" else 1
            except Exception:
                self._status = "error"
                self._blocked_reason = "scheduler history recovery failed"
                self._last_error = self._blocked_reason

    def status(self):
        with self._state_lock:
            return {"state": self._status, "next_run": self._next_run.isoformat() if self._next_run else None,
                    "last_run": dict(self._last_run) if self._last_run else None,
                    "last_outcome": self._last_outcome,
                    "consecutive_failures": self._consecutive_failures,
                    "safety_block_reason": self._blocked_reason,
                    "automatic_orders": "disabled: no concrete reconciliable paper broker is configured"}

    def run_due(self, now=None):
        """Run one due scan. ``now`` and calendar make this deterministic in tests."""
        current = now or self.clock()
        if current.tzinfo is None:
            raise ValueError("Scheduler clock must return a timezone-aware datetime.")
        current = current.astimezone(timezone.utc)
        with self._state_lock:
            if self._status in {"error", "recovering"}:
                return None
            if self._next_run is None:
                self._next_run = current
            if current < self._next_run:
                return None
        if self.config.session_only:
            try:
                eligible = self.calendar.is_open(current)
            except Exception:
                eligible = False
                with self._state_lock:
                    self._blocked_reason = "US exchange session lookup failed"
            if not eligible:
                with self._state_lock:
                    self._status = "blocked" if self._blocked_reason else ("running" if self._running else "stopped")
                    self._next_run = current + timedelta(seconds=self.config.interval_seconds)
                return None
        if not self._lock.acquire(blocking=False):
            return None
        try:
            with self._state_lock:
                self._running = True
                self._status = "running"
                self._blocked_reason = None
            return self._execute(current)
        finally:
            with self._state_lock:
                self._running = False
                self._next_run = current + timedelta(seconds=self.config.interval_seconds)
                if self._status != "error":
                    self._status = ("blocked" if self._blocked_reason else
                                    "running" if self._thread and self._thread.is_alive() else "stopped")
            self._lock.release()

    def _execute(self, started):
        began = time.monotonic()
        result = None
        error = None
        for attempt in range(self.config.retry_attempts):
            try:
                result = self.scanner.scan()
                outcome = "success"
                break
            except Exception as exc:
                # Exception text can contain provider response details or secrets.
                error = f"{type(exc).__name__}: scheduled scan failed"
                outcome = "error"
                logger.warning("scheduled_scan_failed", extra={"attempt": attempt + 1, "error_type": type(exc).__name__})
                if attempt + 1 < self.config.retry_attempts:
                    self.sleep(self.config.retry_delay_seconds)
        ended = self.clock()
        duration = max(0.0, time.monotonic() - began)
        summary = getattr(result, "summary", None)
        summary = dict(summary) if summary is not None else None
        try:
            if self.store:
                self.store.record(started, ended, outcome, duration, error, summary)
        except Exception:
            outcome = "error"
            error = "scheduler run could not be persisted"
            with self._state_lock:
                self._status = "error"
                self._blocked_reason = error
        with self._state_lock:
            self._last_run = {"started_at": started.isoformat(), "ended_at": ended.isoformat(),
                              "outcome": outcome, "duration_seconds": duration, "error": error}
            self._last_outcome = outcome
            self._last_error = error
            self._consecutive_failures = self._consecutive_failures + 1 if outcome == "error" else 0
            if outcome == "error":
                self._blocked_reason = "scheduled scan failed"
        return result

    def start(self):
        with self._state_lock:
            if self._status == "error":
                raise RuntimeError("Scheduler is in error state and cannot start.")
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._next_run = self.clock()
            self._status = "running"
            self._thread = threading.Thread(target=self._loop, name="quantforge-scan-scheduler", daemon=False)
            self._thread.start()

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.run_due()
            except Exception:
                logger.exception("scheduler_tick_failed")
                with self._state_lock:
                    self._status = "error"
                    self._blocked_reason = "scheduler tick failed"
                break
            self._stop.wait(min(self.config.interval_seconds, 1.0))

    def stop(self, timeout=None):
        self._stop.set()
        thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout)
            if thread.is_alive():
                raise TimeoutError("Scheduler did not stop before timeout.")
        with self._state_lock:
            if self._status != "error":
                self._status = "stopped"
        # Open orders are not managed or cancelled by scheduler shutdown.
