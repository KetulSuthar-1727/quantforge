from engine.order import Order


class BacktestEngine:
    def __init__(
        self,
        data,
        strategy,
        portfolio,
        execution_engine,
        position_sizer,
        volatility_model,
        symbol,
    ):
        self.data = data
        self.strategy = strategy
        self.portfolio = portfolio
        self.execution_engine = execution_engine
        self.position_sizer = position_sizer
        self.volatility_model = volatility_model
        self.symbol = symbol

    def run(self):
        result = self.strategy.generate_signal(self.data)
        portfolio_history = []

        for i in range(len(result)):
            row = result.iloc[i]

            # Execute the previous bar's signal at this bar's open.
            if i > 0:
                signal_row = result.iloc[i - 1]
                signal = signal_row["signal"]
                execution_price = row["Open"]

                if signal == "BUY":
                    historical_prices = result.iloc[:i]["Close"].tolist()
                    volatility = self.volatility_model.calculate(
                        prices=historical_prices,
                        window=20,
                    )

                    quantity = 0
                    if volatility > 0:
                        quantity = self.position_sizer.calculate_quantity(
                            available_cash=self.portfolio.cash,
                            price=execution_price,
                            signal_confidence=signal_row["signal_strength"],
                            volatility=volatility,
                        )

                    if quantity > 0:
                        self.execution_engine.execute(
                            Order(
                                symbol=self.symbol,
                                side="BUY",
                                quantity=quantity,
                                price=execution_price,
                            )
                        )

                elif signal == "SELL" and self.portfolio.position > 0:
                    self.execution_engine.execute(
                        Order(
                            symbol=self.symbol,
                            side="SELL",
                            quantity=self.portfolio.position,
                            price=execution_price,
                        )
                    )

            # Value the portfolio at this bar's close.
            portfolio_history.append({
                "date": row["Date"],
                "portfolio_value": self.portfolio.get_value(row["Close"]),
            })

        if result.empty:
            final_value = self.portfolio.cash
        else:
            final_value = self.portfolio.get_value(result.iloc[-1]["Close"])

        return {
            "final_value": final_value,
            "cash": self.portfolio.cash,
            "position": self.portfolio.position,
            "trade_history": self.portfolio.trade_history,
            "portfolio_history": portfolio_history,
        }
