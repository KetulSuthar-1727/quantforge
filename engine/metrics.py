"""Validated portfolio analytics for recorded QuantForge histories.

Daily observations use 252 periods/year. Intraday observations require a regular
bar interval and use 252 * (390 minutes / bar minutes), assuming a US equity
session of 6.5 hours. Calendar CAGR uses elapsed days (365.25/year).
"""

import math
from datetime import date, datetime


class PerformanceMetrics:
    def __init__(self, initial_capital, portfolio_history, trade_history=(), *,
                 timeframe=None, positions=None):
        self.initial_capital = float(initial_capital)
        if not math.isfinite(self.initial_capital) or self.initial_capital <= 0:
            raise ValueError("initial_capital must be a finite positive value")
        self.portfolio_history = list(portfolio_history)
        self.trade_history = list(trade_history)
        self.timeframe = timeframe
        self.positions = list(positions) if positions is not None else None
        self._dates = self._validated_dates()
        self._values = self._validated_values()

    @staticmethod
    def _as_datetime(value):
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time())
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("portfolio history contains an invalid date") from exc
        raise ValueError("portfolio history dates must be dates or ISO date strings")

    def _validated_dates(self):
        dates = []
        for item in self.portfolio_history:
            if "date" in item:
                dates.append(self._as_datetime(item["date"]))
        if len(dates) != len(self.portfolio_history):
            if self.portfolio_history:
                raise ValueError("every portfolio snapshot must have a date")
            return []
        if any(b <= a for a, b in zip(dates, dates[1:])):
            raise ValueError("portfolio history dates must be strictly chronological")
        return dates

    def _validated_values(self):
        values = []
        for snapshot in self.portfolio_history:
            try:
                value = float(snapshot["portfolio_value"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("portfolio snapshots require numeric portfolio_value") from exc
            if not math.isfinite(value):
                raise ValueError("portfolio values must be finite")
            values.append(value)
        return values

    def portfolio_values(self):
        return list(self._values)

    def equity_curve(self):
        return [{"date": d, "portfolio_value": v} for d, v in zip(self._dates, self._values)]

    def cumulative_returns(self):
        if not self._values:
            return None
        return [value / self.initial_capital - 1 for value in self._values]

    def total_return(self):
        return self._values[-1] / self.initial_capital - 1 if self._values else None

    def daily_returns(self):
        returns = []
        for previous, current in zip(self._values, self._values[1:]):
            if previous <= 0:
                raise ValueError("period returns require positive prior portfolio values")
            returns.append(current / previous - 1)
        return returns

    def periods_per_year(self):
        if len(self._dates) < 2:
            return None
        if self.timeframe:
            tf = self.timeframe.lower()
            if tf in ("1day", "1d", "day", "daily"):
                return 252.0
            for unit, factor in (("min", 1), ("hour", 60)):
                if unit in tf:
                    digits = "".join(ch for ch in tf if ch.isdigit())
                    minutes = (int(digits) if digits else 1) * factor
                    if minutes <= 0 or minutes > 390:
                        return None
                    return 252.0 * 390 / minutes
        deltas = [(b - a).total_seconds() for a, b in zip(self._dates, self._dates[1:])]
        median = sorted(deltas)[len(deltas) // 2]
        if median >= 20 * 3600:
            # Date-only/daily input. Require broadly daily cadence.
            return 252.0 if all(20 * 3600 <= d <= 4 * 86400 for d in deltas) else None
        if median > 0:
            minutes = median / 60
            if minutes <= 390 and all(abs(d - median) <= max(1, median * .05) for d in deltas):
                return 252.0 * 390 / minutes
        return None

    def annualized_return(self):
        if len(self._values) < 2 or self.periods_per_year() is None:
            return None
        if self._values[-1] <= 0:
            raise ValueError("annualized return is undefined for a nonpositive final value")
        elapsed = (self._dates[-1] - self._dates[0]).total_seconds() / 86400
        # Very short windows produce unstable CAGR estimates, especially for
        # intraday samples. Require at least a month of observations.
        if elapsed < 30:
            return None
        return (self._values[-1] / self.initial_capital) ** (365.25 / elapsed) - 1

    @staticmethod
    def _sample_std(values):
        if len(values) < 2:
            return None
        mean = sum(values) / len(values)
        return math.sqrt(sum((x - mean) ** 2 for x in values) / (len(values) - 1))

    def annualized_volatility(self):
        annualizer = self.periods_per_year()
        returns = self.daily_returns()
        deviation = self._sample_std(returns)
        return deviation * math.sqrt(annualizer) if deviation is not None and annualizer else None

    def sharpe_ratio(self, risk_free_rate=0.0):
        rate = float(risk_free_rate)
        if not math.isfinite(rate) or rate <= -1:
            raise ValueError("risk_free_rate must be finite and greater than -1")
        annualizer = self.periods_per_year()
        returns = self.daily_returns()
        deviation = self._sample_std(returns)
        if annualizer is None or deviation is None or deviation == 0:
            return None
        period_rf = (1 + rate) ** (1 / annualizer) - 1
        return (sum(returns) / len(returns) - period_rf) / deviation * math.sqrt(annualizer)

    def sortino_ratio(self, risk_free_rate=0.0):
        annualizer = self.periods_per_year()
        returns = self.daily_returns()
        if annualizer is None or len(returns) < 2:
            return None
        rate = float(risk_free_rate)
        if not math.isfinite(rate) or rate <= -1:
            raise ValueError("risk_free_rate must be finite and greater than -1")
        rf = (1 + rate) ** (1 / annualizer) - 1
        excess = [x - rf for x in returns]
        downside = math.sqrt(sum(min(x, 0) ** 2 for x in excess) / len(excess))
        return sum(excess) / len(excess) / downside * math.sqrt(annualizer) if downside else None

    def drawdowns(self):
        peak, output = None, []
        for value in self._values:
            peak = value if peak is None else max(peak, value)
            if peak <= 0:
                raise ValueError("drawdown requires a positive running portfolio peak")
            output.append(value / peak - 1)
        return output

    def maximum_drawdown(self):
        values = self.drawdowns()
        return min(values) if values else None

    def drawdown_duration(self):
        """Return max and current peak-to-recovery duration in observations/days."""
        if not self._values:
            return None
        peak = self._values[0]
        peak_date = self._dates[0]
        current_start = None
        longest_obs = longest_days = 0
        for i, value in enumerate(self._values):
            if value >= peak:
                if current_start is not None:
                    obs = i - current_start
                    days = (self._dates[i] - self._dates[current_start]).total_seconds() / 86400
                    longest_obs, longest_days = max(longest_obs, obs), max(longest_days, days)
                    current_start = None
                peak, peak_date = value, self._dates[i]
            elif current_start is None:
                current_start = max(0, i - 1)
        current_obs = current_days = 0
        if current_start is not None:
            current_obs = len(self._values) - 1 - current_start
            current_days = (self._dates[-1] - self._dates[current_start]).total_seconds() / 86400
        return {"max_observations": max(longest_obs, current_obs),
                "max_days": max(longest_days, current_days),
                "current_observations": current_obs, "current_days": current_days}

    def trade_pnl(self):
        lots, realized = [], []
        for trade in self.trade_history:
            side = trade.get("side")
            try:
                quantity, price = int(trade["quantity"]), float(trade["price"])
                cost = float(trade.get("transaction_cost", 0))
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("trades require quantity, price, and valid costs") from exc
            if quantity < 0 or not all(map(math.isfinite, (price, cost))) or price < 0 or cost < 0:
                raise ValueError("trade quantity, price, and transaction cost must be nonnegative and finite")
            if not quantity:
                continue
            if side == "BUY":
                lots.append([quantity, price + cost / quantity])
            elif side == "SELL":
                remaining, proceeds = quantity, price - cost / quantity
                while remaining and lots:
                    lot = lots[0]
                    matched = min(remaining, lot[0])
                    realized.append((proceeds - lot[1]) * matched)
                    lot[0] -= matched
                    remaining -= matched
                    if lot[0] == 0:
                        lots.pop(0)
            else:
                raise ValueError("trade side must be BUY or SELL")
        return realized

    def win_rate(self):
        pnl = self.trade_pnl()
        return sum(x > 0 for x in pnl) / len(pnl) if pnl else None

    def average_win(self):
        wins = [x for x in self.trade_pnl() if x > 0]
        return sum(wins) / len(wins) if wins else None

    def average_loss(self):
        losses = [x for x in self.trade_pnl() if x < 0]
        return sum(losses) / len(losses) if losses else None

    def profit_factor(self):
        pnl = self.trade_pnl()
        if not pnl:
            return None
        gains = sum(x for x in pnl if x > 0)
        losses = abs(sum(x for x in pnl if x < 0))
        return math.inf if losses == 0 and gains else (gains / losses if losses else None)

    def transaction_costs(self):
        return sum(float(t.get("transaction_cost", 0)) for t in self.trade_history)

    def fees(self):
        """Recorded transaction_cost is commission in current backtest records."""
        return self.transaction_costs()

    def slippage_cost(self):
        # Execution records do not retain reference market prices separately.
        return None

    def trade_count(self):
        return len(self.trade_history)

    def exposure(self):
        if self.positions is None:
            return None
        if len(self.positions) != len(self._values):
            raise ValueError("positions must align with portfolio observations")
        return [abs(float(p)) / v if v else None for p, v in zip(self.positions, self._values)]

    def turnover(self):
        if not self.trade_history:
            return None
        if not self._values:
            return None
        notional = sum(int(t["quantity"]) * float(t["price"]) for t in self.trade_history)
        return notional / (sum(self._values) / len(self._values))


def compare_runs(left, right):
    """Validate run comparability using recorded provenance and aligned dates."""
    lm, rm = left.get("run_metadata", {}), right.get("run_metadata", {})
    lc, rc = lm.get("configuration", {}), rm.get("configuration", {})
    lfp, rfp = lc.get("dataset_fingerprint"), rc.get("dataset_fingerprint")
    if lfp and rfp and lfp != rfp:
        raise ValueError("runs use incompatible dataset fingerprints")
    lh, rh = left.get("portfolio_history", []), right.get("portfolio_history", [])
    ld = [PerformanceMetrics._as_datetime(x["date"]) for x in lh]
    rd = [PerformanceMetrics._as_datetime(x["date"]) for x in rh]
    if ld != rd:
        raise ValueError("runs must have identical observation dates for comparison")
    if lc.get("symbol") and rc.get("symbol") and lc["symbol"] != rc["symbol"]:
        raise ValueError("runs use incompatible symbols")
    return {"run_ids": [lm.get("run_id"), rm.get("run_id")],
            "dataset_fingerprint": lfp or rfp,
            "dates": ld,
            "equity_curves": [[x["portfolio_value"] for x in lh], [x["portfolio_value"] for x in rh]]}
