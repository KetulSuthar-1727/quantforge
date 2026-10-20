"""Fail-closed NYSE regular-session eligibility for US stocks."""
from datetime import timezone


class USMarketCalendar:
    """Uses pandas-market-calendars' NYSE schedule and its DST-aware UTC times."""
    def __init__(self, calendar=None):
        self._calendar = calendar

    def _get_calendar(self):
        if self._calendar is None:
            import pandas_market_calendars as mcal
            self._calendar = mcal.get_calendar("NYSE")
        return self._calendar

    def session(self, now):
        if now.tzinfo is None:
            raise ValueError("Session lookup requires an aware datetime.")
        instant = now.astimezone(timezone.utc)
        date = instant.date().isoformat()
        schedule = self._get_calendar().schedule(start_date=date, end_date=date)
        if schedule is None or len(schedule) != 1:
            return None
        row = schedule.iloc[0]
        opened, closed = row["market_open"], row["market_close"]
        opened = opened.to_pydatetime() if hasattr(opened, "to_pydatetime") else opened
        closed = closed.to_pydatetime() if hasattr(closed, "to_pydatetime") else closed
        if opened.tzinfo is None or closed.tzinfo is None or closed <= opened:
            raise ValueError("Calendar returned invalid session boundaries.")
        return opened.astimezone(timezone.utc), closed.astimezone(timezone.utc)

    def is_open(self, now):
        session = self.session(now)
        if session is None:
            return False
        instant = now.astimezone(timezone.utc)
        opened, closed = session
        return opened <= instant < closed

