from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

PriceBasis = Literal["mid", "buy", "sell"]
OutputEncoding = Literal["json", "msgpack"]


@dataclass(frozen=True, slots=True)
class Tick:
    symbol: str
    buy: float
    sell: float
    timestamp: int
    received_at: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> Tick:
        return cls(
            symbol=str(value["symbol"]),
            buy=float(value["buy"]),
            sell=float(value["sell"]),
            timestamp=int(value["timestamp"]),
            received_at=int(value.get("received_at", value.get("receivedAt", value["timestamp"]))),
        )


@dataclass(frozen=True, slots=True)
class Quote:
    symbol: str
    buy: float
    sell: float
    high_24h: float
    low_24h: float
    change_24h: float
    timestamp: int
    version: int

    def compact(self) -> list[object]:
        return [
            self.symbol,
            self.buy,
            self.sell,
            self.high_24h,
            self.low_24h,
            self.change_24h,
            self.timestamp,
            self.version,
        ]

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "buy": self.buy,
            "sell": self.sell,
            "high24h": self.high_24h,
            "low24h": self.low_24h,
            "change24h": self.change_24h,
            "timestamp": self.timestamp,
            "version": self.version,
        }
