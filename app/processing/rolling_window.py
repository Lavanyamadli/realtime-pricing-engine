from __future__ import annotations

from bisect import bisect_right
from collections import deque

from app.models import PriceBasis, Quote, Tick


class RollingWindow:
    def __init__(
        self,
        symbol: str,
        window_ms: int,
        basis: PriceBasis,
        restored: list[Tick] | None = None,
    ) -> None:
        self.symbol = symbol
        self.window_ms = window_ms
        self.basis = basis
        self._ticks = sorted((tick for tick in (restored or []) if tick.symbol == symbol), key=lambda tick: tick.timestamp)
        self._start = 0
        self._high: deque[Tick] = deque()
        self._low: deque[Tick] = deque()
        self._version = 0
        self._rebuild_deques()

    def _price(self, tick: Tick) -> float:
        if self.basis == "buy":
            return tick.buy
        if self.basis == "sell":
            return tick.sell
        return (tick.buy + tick.sell) / 2

    def add(self, tick: Tick) -> Quote | None:
        newest = self._ticks[-1].timestamp if len(self._ticks) > self._start else tick.timestamp
        cutoff = max(newest, tick.timestamp) - self.window_ms
        if tick.timestamp < cutoff:
            return None

        if len(self._ticks) > self._start and tick.timestamp < newest:
            self._compact()
            index = bisect_right([item.timestamp for item in self._ticks], tick.timestamp)
            self._ticks.insert(index, tick)
            self._prune(cutoff)
            self._rebuild_deques()
        else:
            self._ticks.append(tick)
            self._push_deques(tick)
            self._prune(cutoff)

        self._version += 1
        return self.quote()

    def quote(self) -> Quote | None:
        if self._start >= len(self._ticks) or not self._high or not self._low:
            return None
        first = self._ticks[self._start]
        latest = self._ticks[-1]
        opening = self._price(first)
        closing = self._price(latest)
        return Quote(
            symbol=self.symbol,
            buy=latest.buy,
            sell=latest.sell,
            high_24h=self._price(self._high[0]),
            low_24h=self._price(self._low[0]),
            change_24h=0 if opening == 0 else ((closing - opening) / opening) * 100,
            timestamp=latest.timestamp,
            version=self._version,
        )

    def export_ticks(self) -> list[Tick]:
        return self._ticks[self._start :]

    def _push_deques(self, tick: Tick) -> None:
        price = self._price(tick)
        while self._high and self._price(self._high[-1]) <= price:
            self._high.pop()
        while self._low and self._price(self._low[-1]) >= price:
            self._low.pop()
        self._high.append(tick)
        self._low.append(tick)

    def _prune(self, cutoff: int) -> None:
        while self._start < len(self._ticks) and self._ticks[self._start].timestamp < cutoff:
            self._start += 1
        while self._high and self._high[0].timestamp < cutoff:
            self._high.popleft()
        while self._low and self._low[0].timestamp < cutoff:
            self._low.popleft()
        if self._start > 10_000 and self._start > len(self._ticks) // 2:
            self._compact()

    def _compact(self) -> None:
        if self._start:
            self._ticks = self._ticks[self._start :]
            self._start = 0

    def _rebuild_deques(self) -> None:
        self._high.clear()
        self._low.clear()
        for tick in self._ticks[self._start :]:
            self._push_deques(tick)
