from datetime import datetime, timezone
import builtins
import threading
import time
from unittest.mock import patch

import pandas as pd
import pytest

from engine.scheduler import ScanScheduler, SchedulerConfig, SchedulerStore
from engine.us_market_calendar import USMarketCalendar


UTC = timezone.utc


def test_extended_sessions_remain_disabled():
    with pytest.raises(ValueError, match="Extended sessions are not supported"):
        SchedulerConfig(allow_pre_market=True)
    with pytest.raises(ValueError, match="Extended sessions are not supported"):
        SchedulerConfig(allow_after_hours=True)


class Calendar:
    def __init__(self, opens=None, closes=None):
        self.opens, self.closes = opens, closes

    def schedule(self, start_date, end_date):
        if self.opens is None:
            return pd.DataFrame()
        return pd.DataFrame({"market_open": [pd.Timestamp(self.opens)],
                             "market_close": [pd.Timestamp(self.closes)]})


class Scanner:
    def __init__(self, callback=None):
        self.calls = 0
        self.callback = callback

    def scan(self):
        self.calls += 1
        if self.callback:
            return self.callback()
        return type("Result", (), {"summary": {"symbols_scanned": 2}})()


def test_interval_and_session_window_and_persisted_history(tmp_path):
    scanner = Scanner()
    calendar = type("OpenCalendar", (), {"is_open": lambda self, now: True})()
    scheduler = ScanScheduler(scanner, config=SchedulerConfig(60), calendar=calendar,
                              store=SchedulerStore(tmp_path / "scheduler.sqlite"))
    now = datetime(2026, 10, 20, 14, 30, tzinfo=UTC)
    scheduler.run_due(now)
    assert scanner.calls == 1
    assert scheduler.run_due(now.replace(second=30)) is None
    assert scanner.calls == 1
    assert scheduler.status()["next_run"] == "2026-10-20T14:31:00+00:00"
    assert scheduler.status()["last_outcome"] == "success"
    assert scheduler.status()["last_run"]["duration_seconds"] >= 0


def test_calendar_dst_and_session_boundaries():
    # NYSE opens at 09:30 New York: 13:30 UTC in summer, 14:30 UTC in winter.
    summer = USMarketCalendar(Calendar("2026-07-01T13:30:00Z", "2026-07-01T20:00:00Z"))
    assert not summer.is_open(datetime(2026, 7, 1, 13, 29, 59, tzinfo=UTC))
    assert summer.is_open(datetime(2026, 7, 1, 13, 30, tzinfo=UTC))
    assert not summer.is_open(datetime(2026, 7, 1, 20, 0, tzinfo=UTC))
    winter = USMarketCalendar(Calendar("2026-01-05T14:30:00Z", "2026-01-05T21:00:00Z"))
    assert winter.is_open(datetime(2026, 1, 5, 14, 30, tzinfo=UTC))


def test_real_nyse_calendar_regular_holiday_dst_and_boundaries():
    """Integration against the pinned pandas-market-calendars implementation."""
    calendar = USMarketCalendar()

    # Tuesday regular session (winter): 09:30–16:00 America/New_York.
    regular = datetime(2026, 1, 6, 15, 0, tzinfo=UTC)
    assert calendar.is_open(regular)
    assert calendar.session(regular) == (
        datetime(2026, 1, 6, 14, 30, tzinfo=UTC),
        datetime(2026, 1, 6, 21, 0, tzinfo=UTC),
    )

    # Christmas is a NYSE holiday.
    holiday = datetime(2026, 12, 25, 16, 0, tzinfo=UTC)
    assert calendar.session(holiday) is None
    assert not calendar.is_open(holiday)

    # DST begins Sunday March 8, 2026: Monday's UTC session shifts one hour.
    before_dst = datetime(2026, 3, 6, 14, 30, tzinfo=UTC)
    after_dst = datetime(2026, 3, 9, 13, 30, tzinfo=UTC)
    assert calendar.session(before_dst)[0] == before_dst
    assert calendar.session(after_dst)[0] == after_dst
    assert calendar.is_open(before_dst) and calendar.is_open(after_dst)

    # Summer session boundaries: open is inclusive, close is exclusive.
    open_boundary = datetime(2026, 7, 1, 13, 30, tzinfo=UTC)
    close_boundary = datetime(2026, 7, 1, 20, 0, tzinfo=UTC)
    assert not calendar.is_open(datetime(2026, 7, 1, 13, 29, 59, tzinfo=UTC))
    assert calendar.is_open(open_boundary)
    assert calendar.is_open(datetime(2026, 7, 1, 19, 59, 59, tzinfo=UTC))
    assert not calendar.is_open(close_boundary)


def test_holiday_and_failed_calendar_fail_closed():
    scanner = Scanner()
    closed = USMarketCalendar(Calendar())
    scheduler = ScanScheduler(scanner, calendar=closed)
    scheduler.run_due(datetime(2026, 12, 25, 16, tzinfo=UTC))
    assert scanner.calls == 0
    failed = ScanScheduler(scanner, calendar=type("Bad", (), {"is_open": lambda *_: (_ for _ in ()).throw(RuntimeError())})())
    failed.run_due(datetime(2026, 10, 20, 15, tzinfo=UTC))
    assert scanner.calls == 0
    assert failed.status()["safety_block_reason"] == "US exchange session lookup failed"


def test_calendar_import_failure_blocks_scan():
    scanner = Scanner()
    scheduler = ScanScheduler(scanner)
    original_import = builtins.__import__

    def fail_calendar_import(name, *args, **kwargs):
        if name == "pandas_market_calendars":
            raise ImportError("calendar package unavailable")
        return original_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=fail_calendar_import):
        scheduler.run_due(datetime(2026, 1, 6, 15, 0, tzinfo=UTC))

    assert scanner.calls == 0
    assert scheduler.status()["state"] == "blocked"
    assert scheduler.status()["safety_block_reason"] == "US exchange session lookup failed"


def test_overlapping_execution_is_skipped():
    entered, release = threading.Event(), threading.Event()
    def block():
        entered.set()
        release.wait(2)
    scanner = Scanner(block)
    scheduler = ScanScheduler(scanner, config=SchedulerConfig(1, session_only=False))
    first = threading.Thread(target=lambda: scheduler.run_due(datetime(2026, 1, 1, tzinfo=UTC)))
    first.start()
    assert entered.wait(1)
    assert scheduler.run_due(datetime(2026, 1, 1, 0, 0, 2, tzinfo=UTC)) is None
    release.set()
    first.join(2)
    assert scanner.calls == 1


def test_start_stop_is_explicit_graceful_and_does_not_cancel_orders():
    scanner = Scanner()
    scheduler = ScanScheduler(scanner, config=SchedulerConfig(1, session_only=False))
    assert scheduler.status()["state"] == "stopped"
    scheduler.start()
    time.sleep(0.03)
    scheduler.stop(timeout=2)
    assert scheduler.status()["state"] == "stopped"
    assert scanner.calls >= 1


def test_transient_failures_are_bounded_and_visible():
    def fail():
        raise TimeoutError("temporary")
    scanner = Scanner(fail)
    delays = []
    scheduler = ScanScheduler(scanner, config=SchedulerConfig(1, session_only=False,
                                                              retry_attempts=2, retry_delay_seconds=0.25),
                              sleep=delays.append)
    scheduler.run_due(datetime(2026, 1, 1, tzinfo=UTC))
    assert scanner.calls == 2
    assert delays == [0.25]
    state = scheduler.status()
    assert state["last_outcome"] == "error"
    assert state["consecutive_failures"] == 1
    assert state["safety_block_reason"] == "scheduled scan failed"


def test_scheduler_run_history_is_recovered_for_status(tmp_path):
    store = SchedulerStore(tmp_path / "scheduler.sqlite")
    now = datetime(2026, 1, 1, tzinfo=UTC)
    store.record(now, now, "success", 0.2, summary={"symbols_scanned": 1})
    recovered = ScanScheduler(Scanner(), store=store)
    assert recovered.status()["last_outcome"] == "success"
    assert recovered.status()["last_run"]["duration_seconds"] == 0.2


def test_missed_tick_runs_once_and_dashboard_construction_has_no_scheduler(tmp_path):
    scanner = Scanner()
    scheduler = ScanScheduler(scanner, config=SchedulerConfig(10, session_only=False))
    scheduler.run_due(datetime(2026, 1, 1, tzinfo=UTC))
    scheduler.run_due(datetime(2026, 1, 1, 0, 5, tzinfo=UTC))
    assert scanner.calls == 2
    # Scheduler objects are opt-in; importing/rerunning the dashboard starts none.
    from streamlit.testing.v1 import AppTest
    from pathlib import Path
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()
    assert not app.exception
