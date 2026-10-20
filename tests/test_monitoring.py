import logging
from datetime import datetime, timezone, timedelta

import pandas as pd
from urllib.error import URLError
from unittest.mock import patch

from engine.market_data import AlpacaMarketDataProvider
from engine.monitoring import ContextFormatter, MonitoringMetrics, SensitiveRedactionFilter, configure_logging, health_report
from engine.scanner import StockScanner
from strategies.moving_average import MovingAverageStrategy


def bars():
    values = [5.0, 4.0, 3.0]
    return pd.DataFrame({"Date": pd.date_range("2026-01-01", periods=3, tz="UTC"),
                         "Open": values, "High": values, "Low": values,
                         "Close": values, "Volume": [1, 1, 1]})


def test_logging_uses_local_readable_format_and_configurable_level(caplog):
    configure_logging("WARNING")
    record = logging.LogRecord("quantforge", logging.INFO, "", 1, "scan_completed", (), None)
    record.component = "scanner"
    record.run_id = "r-1"
    SensitiveRedactionFilter().filter(record)
    formatted = ContextFormatter("%(asctime)s %(levelname)s %(name)s %(message)s").format(record)
    assert "INFO quantforge scan_completed" in formatted
    assert "component=scanner" in formatted and "run_id=r-1" in formatted
    sensitive = logging.LogRecord("quantforge", logging.WARNING, "", 1,
                                  "request failed api_key=top-secret Authorization: Bearer secret-token", (), None)
    SensitiveRedactionFilter().filter(sensitive)
    formatted_sensitive = ContextFormatter("%(message)s").format(sensitive)
    assert "top-secret" not in formatted_sensitive and "secret-token" not in formatted_sensitive
    assert "api_key=[REDACTED]" in formatted_sensitive
    assert logging.getLogger().level == logging.WARNING
    configure_logging("INFO")


def test_scan_logs_success_and_failure_and_metrics_are_consistent(caplog):
    metrics = MonitoringMetrics()
    scanner = StockScanner(["AAPL", "MSFT"], MovingAverageStrategy(1, 2),
                           lambda symbol: bars() if symbol == "AAPL" else (_ for _ in ()).throw(RuntimeError("secret-value")),
                           metrics=metrics)
    with caplog.at_level(logging.INFO):
        result = scanner.scan()
    assert result.summary["error"] == 1
    assert "scan_started" in [record.getMessage() for record in caplog.records]
    assert "scan_completed" in [record.getMessage() for record in caplog.records]
    assert "symbol_scan_failed" in [record.getMessage() for record in caplog.records]
    assert "secret-value" not in caplog.text
    state = metrics.snapshot()["scans"]
    assert (state["total"], state["successful"], state["failed"], state["consecutive_failures"]) == (1, 0, 1, 1)
    assert state["last_duration_seconds"] >= 0
    assert state["last_outcome"] == "failed"
    assert health_report(metrics=metrics)["checks"]["scanner"]["state"] == "degraded"
    caplog.clear()
    successful = StockScanner(["AAPL"], MovingAverageStrategy(1, 2), lambda _: bars(), metrics=metrics)
    with caplog.at_level(logging.INFO):
        successful.scan()
    completed = [record for record in caplog.records if record.getMessage() == "scan_completed"]
    assert len(completed) == 1 and completed[0].outcome == "success"
    assert metrics.snapshot()["scans"]["consecutive_failures"] == 0
    metrics.record_scan("success", 0.1)
    assert metrics.snapshot()["scans"]["consecutive_failures"] == 0
    assert health_report(metrics=metrics)["checks"]["scanner"]["state"] == "healthy"


def test_health_calendar_provider_block_and_scheduler_states(monkeypatch):
    metrics = MonitoringMetrics()
    monkeypatch.setattr("engine.monitoring.importlib.import_module", lambda name: (_ for _ in ()).throw(ImportError())
                        if name == "pandas_market_calendars" else __import__(name))
    report = health_report(metrics=metrics)
    assert report["checks"]["market_calendar"]["state"] == "unhealthy"
    assert report["checks"]["market_data"]["state"] == "unavailable"
    assert report["checks"]["broker"]["state"] == "unavailable"
    assert report["status"] == "unhealthy"

    class Scheduler:
        def status(self):
            return {"state": "blocked", "safety_block_reason": "US exchange session lookup failed", "last_outcome": None}
    report = health_report(scheduler=Scheduler(), metrics=MonitoringMetrics())
    assert report["checks"]["scheduler"]["state"] == "blocked"
    assert report["status"] == "blocked"


def test_market_data_failure_and_staleness_metrics_and_restart_reset():
    metrics = MonitoringMetrics()
    metrics.record_data_fetch("failed", 0.4, symbol="AAPL")
    assert metrics.snapshot()["market_data"]["failures"] == 1
    old = datetime.now(timezone.utc) - timedelta(hours=1)
    metrics.record_data_fetch("success", 0.2, symbol="AAPL", timestamp=old)
    market = metrics.snapshot()["market_data"]
    assert market["failures"] == 1
    assert market["last_outcome"] == "success"
    assert market["latest_age_seconds"] >= 3599
    metrics.reset()
    assert metrics.snapshot()["scans"]["total"] == 0
    assert metrics.snapshot()["market_data"]["fetches"] == 0


def test_provider_failure_is_measured_without_logging_credentials(caplog):
    metrics = MonitoringMetrics()
    provider = AlpacaMarketDataProvider(api_key="api-secret", secret_key="secret-secret", metrics=metrics)
    provider.MAX_RETRIES = 0
    with patch("engine.market_data.alpaca.urlopen", side_effect=URLError("secret-secret")), caplog.at_level(logging.WARNING):
        try:
            provider.fetch_bars("AAPL", "1Min")
        except Exception:
            pass
        else:
            raise AssertionError("provider failure was expected")
    assert metrics.snapshot()["market_data"]["failures"] == 1
    assert metrics.snapshot()["market_data"]["last_outcome"] == "failed"
    assert "secret-secret" not in caplog.text
    assert "market_data_fetch_failed" in caplog.text


def test_health_provider_credentials_do_not_mean_connected():
    metrics = MonitoringMetrics()
    report = health_report(provider_configured=True, metrics=metrics)
    assert report["checks"]["market_data"]["state"] == "degraded"
    metrics.record_data_fetch("failed", 0.1, symbol="AAPL")
    assert health_report(provider_configured=True, metrics=metrics)["checks"]["market_data"]["state"] == "degraded"
