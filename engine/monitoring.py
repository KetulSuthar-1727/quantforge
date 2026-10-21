"""Small in-process monitoring primitives for local QuantForge workflows.

Counters and durations are process-local and reset when the Python process
restarts. Scheduler run history remains separately persisted by SchedulerStore.
"""
from collections import deque
from datetime import datetime, timezone
import importlib
import logging
import re
import threading
import time
import atexit

logger = logging.getLogger(__name__)
_shutdown_registered = False
_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key(?:[_-]?id)?|secret[_-]?key|authorization|access[_-]?token|password)(\s*[:=]\s*)([^\s,;&]+)"),
    re.compile(r"(?i)\bBearer\s+[^\s,;&]+"),
)


def _redact(value):
    value = str(value)
    value = _SECRET_PATTERNS[1].sub("Bearer [REDACTED]", value)
    return _SECRET_PATTERNS[0].sub(lambda match: match.group(1) + match.group(2) + "[REDACTED]", value)


class SensitiveRedactionFilter(logging.Filter):
    def filter(self, record):
        record.msg = _redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {key: _redact(value) for key, value in record.args.items()}
            else:
                record.args = tuple(_redact(value) for value in record.args)
        return True


class MonitoringMetrics:
    def __init__(self, recent_limit=20):
        self._lock = threading.RLock()
        self.recent_limit = recent_limit
        self.reset()

    def reset(self):
        with getattr(self, "_lock", threading.RLock()):
            self.scan_total = self.scan_success = self.scan_failed = 0
            self.scan_consecutive_failures = 0
            self.scan_duration_seconds = None
            self.last_scan_at = self.last_successful_scan_at = None
            self.last_scan_outcome = None
            self.recent_scan_errors = deque(maxlen=self.recent_limit)
            self.data_fetch_total = self.data_fetch_failures = 0
            self.data_fetch_duration_seconds = None
            self.last_data_fetch_at = self.last_data_timestamp = None
            self.last_data_fetch_outcome = None
            self.last_data_symbol = None
            self.safety_block_reason = None

    def record_scan(self, outcome, duration, error=None, *, run_id=None, at=None):
        timestamp = (at or datetime.now(timezone.utc)).isoformat()
        with self._lock:
            self.scan_total += 1
            self.scan_duration_seconds = max(0.0, float(duration))
            self.last_scan_at, self.last_scan_outcome = timestamp, outcome
            if outcome == "success":
                self.scan_success += 1
                self.scan_consecutive_failures = 0
                self.last_successful_scan_at = timestamp
                self.safety_block_reason = None
            else:
                self.scan_failed += 1
                self.scan_consecutive_failures += 1
                self.safety_block_reason = "scan failed"
                if error:
                    self.recent_scan_errors.append({"at": timestamp, "run_id": run_id, "error": str(error)})

    def record_data_fetch(self, outcome, duration, *, symbol=None, timestamp=None):
        with self._lock:
            self.data_fetch_total += 1
            self.data_fetch_duration_seconds = max(0.0, float(duration))
            self.last_data_fetch_at = datetime.now(timezone.utc).isoformat()
            self.last_data_fetch_outcome = outcome
            self.last_data_symbol = symbol
            if outcome == "success":
                self.last_data_timestamp = timestamp.isoformat() if hasattr(timestamp, "isoformat") else timestamp
            else:
                self.data_fetch_failures += 1

    def snapshot(self):
        with self._lock:
            age = None
            if self.last_data_timestamp:
                try:
                    stamp = datetime.fromisoformat(str(self.last_data_timestamp).replace("Z", "+00:00"))
                    age = max(0.0, (datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds())
                except (ValueError, TypeError):
                    pass
            return {
                "scans": {"total": self.scan_total, "successful": self.scan_success,
                          "failed": self.scan_failed, "consecutive_failures": self.scan_consecutive_failures,
                          "last_duration_seconds": self.scan_duration_seconds,
                          "last_scan_at": self.last_scan_at, "last_successful_scan_at": self.last_successful_scan_at,
                          "last_outcome": self.last_scan_outcome,
                          "recent_errors": list(self.recent_scan_errors)},
                "market_data": {"fetches": self.data_fetch_total, "failures": self.data_fetch_failures,
                                "last_duration_seconds": self.data_fetch_duration_seconds,
                                "last_fetch_at": self.last_data_fetch_at, "last_outcome": self.last_data_fetch_outcome,
                                "last_symbol": self.last_data_symbol, "latest_timestamp": self.last_data_timestamp,
                                "latest_age_seconds": age},
                "safety_block_reason": self.safety_block_reason,
                "reset_policy": "process restart resets counters; scheduler run history is persisted separately",
            }


METRICS = MonitoringMetrics()


def health_report(*, scheduler=None, provider_configured=False, persistence_path=None, metrics=None):
    """Report observable local state; credential presence is not connectivity."""
    metrics = metrics or METRICS
    snapshot = metrics.snapshot()
    checks = {"runtime": {"state": "healthy", "detail": "Python process is serving this dashboard."},
              "market_calendar": {"state": "healthy", "detail": "pandas-market-calendars is importable."},
              "market_data": {"state": "unavailable", "detail": "No provider fetch outcome is available."},
              "scanner": {"state": "unavailable", "detail": "No scan outcome is available."},
              "scheduler": {"state": "stopped", "detail": "No active scheduler was supplied."},
              "persistence": {"state": "stopped", "detail": "No monitoring persistence store is configured."},
              "cpp_engine": {"state": "unavailable", "detail": "C++ engine is not required for dashboard scanning."},
              "broker": {"state": "unavailable", "detail": "No concrete broker adapter is configured."}}
    try:
        importlib.import_module("pandas_market_calendars")
    except Exception:
        checks["market_calendar"] = {"state": "unhealthy", "detail": "Required market-calendar dependency is unavailable; scheduled scans fail closed."}
    if snapshot["market_data"]["last_outcome"]:
        ok = snapshot["market_data"]["last_outcome"] == "success"
        checks["market_data"] = {"state": "healthy" if ok else "degraded",
                                  "detail": "Last fetch succeeded." if ok else "Last fetch failed."}
    elif provider_configured:
        checks["market_data"] = {"state": "degraded", "detail": "Provider is configured but has not completed a fetch."}
    if snapshot["scans"]["last_outcome"]:
        failed = snapshot["scans"]["last_outcome"] != "success"
        checks["scanner"] = {"state": "degraded" if failed else "healthy",
                              "detail": "Most recent scan included symbol errors." if failed else "Most recent scan completed without symbol errors."}
    if scheduler is not None:
        status = scheduler.status()
        state = status["state"]
        if state == "error": state = "unhealthy"
        checks["scheduler"] = {"state": state, "detail": status.get("safety_block_reason") or
                                f"Last outcome: {status.get('last_outcome') or 'none'}.", "status": status}
    if persistence_path:
        try:
            import os
            folder = os.path.dirname(os.path.abspath(str(persistence_path)))
            if os.path.isdir(folder) and os.access(folder, os.W_OK):
                checks["persistence"] = {"state": "healthy", "detail": "Configured persistence directory is writable."}
            else:
                checks["persistence"] = {"state": "unhealthy", "detail": "Configured persistence directory is unavailable or not writable."}
        except OSError:
            checks["persistence"] = {"state": "unhealthy", "detail": "Persistence availability check failed."}
    states = [item["state"] for item in checks.values() if item["state"] not in {"unavailable", "stopped"}]
    overall = "blocked" if "blocked" in states else "unhealthy" if "unhealthy" in states else "degraded" if "degraded" in states else "healthy"
    if checks["scheduler"]["state"] == "stopped" and overall == "healthy":
        overall = "stopped"
    return {"status": overall, "checks": checks, "metrics": snapshot}


def configure_logging(level=None):
    """Configure readable local console logs without changing existing handlers."""
    import os
    chosen = (level or os.getenv("QUANTFORGE_LOG_LEVEL", "INFO")).upper()
    numeric = getattr(logging, chosen, logging.INFO)
    handler_format = ContextFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.basicConfig(level=numeric, handlers=[logging.StreamHandler()], force=False)
    for handler in logging.getLogger().handlers:
        handler.setFormatter(handler_format)
        handler.addFilter(SensitiveRedactionFilter())
    logging.getLogger().setLevel(numeric)
    global _shutdown_registered
    if not _shutdown_registered:
        atexit.register(lambda: logging.getLogger(__name__).info(
            "application_shutdown", extra={"component": "runtime"}))
        _shutdown_registered = True


def monotonic():
    return time.monotonic()


class ContextFormatter(logging.Formatter):
    """Append a fixed allowlist of operational context fields to console logs."""
    fields = ("component", "run_id", "symbol", "interval", "duration_seconds", "outcome",
              "error_category", "attempt", "reason", "symbols", "symbols_scanned",
              "symbol_errors", "bar_count", "latest_timestamp", "interval_seconds", "kill_switch")

    def format(self, record):
        message = super().format(record)
        context = [f"{name}={getattr(record, name)}" for name in self.fields if hasattr(record, name)]
        return message + (" " + " ".join(context) if context else "")
