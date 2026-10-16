import math
from datetime import date, datetime


class PerformanceMetrics:
    def __init__(
        self,
        initial_capital,
        portfolio_history,
        trade_history,
    ):
        self.initial_capital = initial_capital
        self.portfolio_history = portfolio_history
        self.trade_history = trade_history

    def portfolio_values(self):
        return [
            float(snapshot["portfolio_value"])
            for snapshot in self.portfolio_history
        ]

    def total_return(self):
        if self.initial_capital <= 0 or not self.portfolio_history:
            return 0.0

        final_value = self.portfolio_values()[-1]
        return final_value / self.initial_capital - 1.0

    def daily_returns(self):
        values = self.portfolio_values()
        returns = []

        for previous, current in zip(values, values[1:]):
            if previous <= 0:
                returns.append(0.0)
            else:
                returns.append(current / previous - 1.0)

        return returns

    def annualized_return(self):
        if self.initial_capital <= 0 or not self.portfolio_history:
            return 0.0

        final_value = self.portfolio_values()[-1]
        if final_value <= 0:
            return -1.0

        start_date = self.portfolio_history[0]["date"]
        end_date = self.portfolio_history[-1]["date"]

        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date)

        days = (end_date - start_date).days
        if days <= 0:
            return self.total_return()

        years = days / 365.25
        return (final_value / self.initial_capital) ** (1.0 / years) - 1.0

    def annualized_volatility(self):
        returns = self.daily_returns()
        if len(returns) < 2:
            return 0.0

        mean_return = sum(returns) / len(returns)
        variance = sum(
            (value - mean_return) ** 2 for value in returns
        ) / (len(returns) - 1)

        return math.sqrt(variance) * math.sqrt(252)

    def sharpe_ratio(self, risk_free_rate=0.0):
        returns = self.daily_returns()
        if len(returns) < 2:
            return 0.0

        daily_rf = risk_free_rate / 252.0
        excess = [value - daily_rf for value in returns]
        mean_excess = sum(excess) / len(excess)

        mean_return = sum(returns) / len(returns)
        variance = sum(
            (value - mean_return) ** 2 for value in returns
        ) / (len(returns) - 1)
        volatility = math.sqrt(variance)

        if volatility == 0:
            return 0.0

        return mean_excess / volatility * math.sqrt(252)

    def sortino_ratio(self, risk_free_rate=0.0):
        returns = self.daily_returns()
        if len(returns) < 2:
            return 0.0

        daily_rf = risk_free_rate / 252.0
        excess = [value - daily_rf for value in returns]
        mean_excess = sum(excess) / len(excess)

        # Downside deviation is measured across all periods relative
        # to the minimum acceptable return (the daily risk-free rate).
        downside_variance = sum(
            min(value, 0.0) ** 2 for value in excess
        ) / len(excess)
        downside_deviation = math.sqrt(downside_variance)

        if downside_deviation == 0:
            return 0.0

        return mean_excess / downside_deviation * math.sqrt(252)

    def maximum_drawdown(self):
        values = self.portfolio_values()
        if not values:
            return 0.0

        peak = values[0]
        max_drawdown = 0.0

        for value in values:
            peak = max(peak, value)
            if peak > 0:
                drawdown = value / peak - 1.0
                max_drawdown = min(max_drawdown, drawdown)

        return max_drawdown

    def trade_pnl(self):
        """Return realized P&L per closed position, including trade costs.

        Supports multiple entries and partial exits using FIFO matching.
        Each trade's transaction_cost is allocated proportionally across
        its quantity. P&L is based on recorded execution prices.
        """
        lots = []
        realized = []

        for trade in self.trade_history:
            side = trade.get("side")
            quantity = int(trade.get("quantity", 0))
            price = float(trade.get("price", 0.0))
            total_cost = float(trade.get("transaction_cost", 0.0))

            if quantity <= 0:
                continue

            cost_per_unit = total_cost / quantity

            if side == "BUY":
                lots.append({
                    "quantity": quantity,
                    "unit_cost": price + cost_per_unit,
                })

            elif side == "SELL":
                remaining = quantity
                sell_unit_proceeds = price - cost_per_unit

                while remaining > 0 and lots:
                    lot = lots[0]
                    matched = min(remaining, lot["quantity"])

                    realized.append(
                        (sell_unit_proceeds - lot["unit_cost"]) * matched
                    )

                    lot["quantity"] -= matched
                    remaining -= matched

                    if lot["quantity"] == 0:
                        lots.pop(0)

        return realized

    def win_rate(self):
        pnl = self.trade_pnl()
        if not pnl:
            return 0.0
        return sum(value > 0 for value in pnl) / len(pnl)

    def average_win(self):
        winners = [value for value in self.trade_pnl() if value > 0]
        return sum(winners) / len(winners) if winners else 0.0

    def average_loss(self):
        losers = [value for value in self.trade_pnl() if value < 0]
        return sum(losers) / len(losers) if losers else 0.0

    def profit_factor(self):
        pnl = self.trade_pnl()
        gross_profit = sum(value for value in pnl if value > 0)
        gross_loss = abs(sum(value for value in pnl if value < 0))

        if gross_loss == 0:
            return math.inf if gross_profit > 0 else 0.0

        return gross_profit / gross_loss
