"""Validated, ordered symbol collections for US-equity research."""
import re


class StockUniverse:
    def __init__(self, symbols):
        if isinstance(symbols, str):
            symbols = symbols.split(",")
        normalized = []
        seen = set()
        for symbol in symbols:
            if not isinstance(symbol, str):
                raise ValueError("Each symbol must be a string.")
            value = symbol.strip().upper()
            if not re.fullmatch(r"[A-Z0-9.-]{1,20}", value):
                raise ValueError(f"Malformed stock symbol: {symbol!r}.")
            if value not in seen:
                seen.add(value)
                normalized.append(value)
        if not normalized:
            raise ValueError("Stock universe must contain at least one symbol.")
        self.symbols = tuple(normalized)

    def __iter__(self):
        return iter(self.symbols)

    def __len__(self):
        return len(self.symbols)
