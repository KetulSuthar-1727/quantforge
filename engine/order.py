from dataclasses import dataclass

@dataclass
class Order:
    symbol: str
    side: str
    quantity: int
    price: float