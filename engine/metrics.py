"""Performance statistics for portfolio and execution histories."""

import math
from datetime import date, datetime


class PerformanceMetrics:
    """Calculate returns, risk, and FIFO realized P&L from a backtest.

    Risk-free rates are annual decimal rates. Portfolio history is expected
    to contain dated ``portfolio_value`` snapshots in chronological order.
    """

    def __init__(self, initial_capital, portfolio_history, trade_history):
        self.initial_capital = float(initial_capital)
        if not math.isfinite(self.initial_capital) or self.initial_capital <= 0:
            raise ValueError("initial_capital must be a finite positive value")
        self.portfolio_history = list(portfolio_history)
        self.trade_history = list(trade_history)

    def portfolio_values(self):
        values = []
        for snapshot in self.portfolio_history:
            value = float(snapshot["portfolio_value"])
            if not math.isfinite(value):
                raise ValueError("portfolio values must be finite")
            values.append(value)
        return values

    def total_return(self):
        values = self.portfolio_values()
        return values[-1] / self.initial_capital - 1 if values else 0.0

    def daily_returns(self):
        """Return simple period-to-period returns; zero/nonpositive bases fail."""
        values = self.portfolio_values()
        returns = []
        for previous, current in zip(values, values[1:]):
            if previous <= 0:
                raise ValueError("daily returns require positive prior portfolio values")
            returns.append(current / previous - 1.0)
        return returns

    @staticmethod
    def _as_datetime(value):
        if isinstance(value, date) and not isinstance(value, datetime):
            return datetime.combine(value, datetime.min.time())
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("portfolio history contains an invalid date") from exc
        raise ValueError("portfolio history dates must be dates or ISO date strings")

    def annualized_return(self):
        """CAGR from initial capital to final value over elapsed calendar time.

        A nonpositive ending value has no meaningful fractional CAGR and raises
        ValueError. Histories spanning zero elapsed time report total return.
        """
        if not self.portfolio_history:
            return 0.0
        values = self.portfolio_values()
        dates = [self._as_datetime(snapshot["date"]) for snapshot in self.portfolio_history]
        if any(later < earlier for earlier, later in zip(dates, dates[1:])):
            raise ValueError("portfolio history dates must be chronological")
        start, end = dates[0], dates[-1]
        if values[-1] <= 0:
            raise ValueError("annualized return is undefined for a nonpositive final value")
        elapsed_days = (end - start).total_seconds() / 86400
        if elapsed_days == 0:
            return self.total_return()
        years = elapsed_days / 365.25
        return (values[-1] / self.initial_capital) ** (1.0 / years) - 1.0

    @staticmethod
    def _sample_std(values):
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        deviation = math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))
        return 0.0 if deviation < 1e-15 else deviation

    def annualized_volatility(self):
        return self._sample_std(self.daily_returns()) * math.sqrt(252)

    @staticmethod
    def _daily_risk_free_rate(risk_free_rate):
        rate = float(risk_free_rate)
        if not math.isfinite(rate) or rate <= -1:
            raise ValueError("risk_free_rate must be finite and greater than -1")
        return (1.0 + rate) ** (1.0 / 252.0) - 1.0

    def sharpe_ratio(self, risk_free_rate=0.0):
        returns = self.daily_returns()
        if len(returns) < 2:
            return 0.0
        excess_mean = sum(returns) / len(returns) - self._daily_risk_free_rate(risk_free_rate)
        deviation = self._sample_std(returns)
        return excess_mean / deviation * math.sqrt(252) if deviation else 0.0

    def sortino_ratio(self, risk_free_rate=0.0):
        returns = self.daily_returns()
        if not returns:
            return 0.0
        daily_rf = self._daily_risk_free_rate(risk_free_rate)
        excess = [value - daily_rf for value in returns]
        downside = math.sqrt(sum(min(value, 0.0) ** 2 for value in excess) / len(excess))
        return (sum(excess) / len(excess)) / downside * math.sqrt(252) if downside > 1e-15 else 0.0

    def drawdowns(self):
        """Return peak-relative drawdowns aligned to portfolio snapshots.

        Every observation must have a positive running peak. Histories that
        start at or below zero have no valid peak-relative drawdown baseline,
        so they raise ValueError instead of reporting a misleading zero.
        """
        values = self.portfolio_values()
        peak = None
        output = []
        for value in values:
            peak = value if peak is None else max(peak, value)
            if peak <= 0:
                raise ValueError("drawdown requires a positive running portfolio peak")
            output.append(value / peak - 1.0)
        return output

    def maximum_drawdown(self):
        return min(self.drawdowns(), default=0.0)

    def trade_pnl(self):
        """Return FIFO realized P&L per matched quantity block, net of costs.

        Entry and exit commission is allocated per share. Unmatched buys remain
        open and are excluded; sells beyond recorded long inventory are ignored.
        """
        lots = []
        realized = []
        for trade in self.trade_history:
            side = trade.get("side")
            quantity = int(trade.get("quantity", 0))
            price = float(trade.get("price", 0.0))
            cost = float(trade.get("transaction_cost", 0.0))
            if quantity < 0 or not all(map(math.isfinite, (price, cost))) or price < 0 or cost < 0:
                raise ValueError("trade quantity, price, and transaction cost must be nonnegative")
            if quantity == 0:
                continue
            if side == "BUY":
                lots.append([quantity, price + cost / quantity])
            elif side == "SELL":
                remaining = quantity
                proceeds = price - cost / quantity
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
        return sum(value > 0 for value in pnl) / len(pnl) if pnl else 0.0

    def average_win(self):
        wins = [value for value in self.trade_pnl() if value > 0]
        return sum(wins) / len(wins) if wins else 0.0

    def average_loss(self):
        losses = [value for value in self.trade_pnl() if value < 0]
        return sum(losses) / len(losses) if losses else 0.0

    def profit_factor(self):
        pnl = self.trade_pnl()
        gains = sum(value for value in pnl if value > 0)
        losses = abs(sum(value for value in pnl if value < 0))
        if losses == 0:
            return math.inf if gains > 0 else 0.0
        return gains / losses
