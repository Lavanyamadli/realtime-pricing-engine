from __future__ import annotations

import hashlib
import time

from app.metrics import Metrics
from app.models import PriceBasis, Quote, Tick
from app.processing.rolling_window import RollingWindow


class PricingEngine:
    def __init__(self, window_ms: int, basis: PriceBasis, dedupe_ttl_ms: int, metrics: Metrics) -> None:
        self.window_ms = window_ms
        self.basis = basis
        self.dedupe_ttl_ms = dedupe_ttl_ms
        self.metrics = metrics
        self._windows: dict[str, RollingWindow] = {}
        self._seen: dict[str, int] = {}

    @staticmethod
    def _fingerprint(tick: Tick) -> str:
        value = f"{tick.symbol}|{tick.timestamp}|{tick.buy}|{tick.sell}".encode()
        return hashlib.sha1(value, usedforsecurity=False).hexdigest()

    def restore(self, symbols: dict[str, list[Tick]]) -> None:
        now = int(time.time() * 1000)
        for symbol, ticks in symbols.items():
            self._windows[symbol] = RollingWindow(symbol, self.window_ms, self.basis, ticks)
            for tick in ticks:
                expiry = tick.received_at + self.dedupe_ttl_ms
                if expiry >= now:
                    self._seen[self._fingerprint(tick)] = expiry
        self.metrics.gauge("pricing_symbols", len(self._windows))

    def process(self, tick: Tick) -> Quote | None:
        fingerprint = self._fingerprint(tick)
        expiry = self._seen.get(fingerprint)
        if expiry is not None and expiry >= tick.received_at:
            self.metrics.increment("pricing_duplicates_total")
            return None
        self._seen[fingerprint] = tick.received_at + self.dedupe_ttl_ms
        if len(self._seen) > 100_000:
            self._seen = {key: value for key, value in self._seen.items() if value >= tick.received_at}

        window = self._windows.get(tick.symbol)
        if window is None:
            window = RollingWindow(tick.symbol, self.window_ms, self.basis)
            self._windows[tick.symbol] = window
            self.metrics.gauge("pricing_symbols", len(self._windows))
        previous_timestamp = window.quote().timestamp if window.quote() else None
        quote = window.add(tick)
        if quote is None:
            self.metrics.increment("pricing_stale_ticks_total")
            return None
        if previous_timestamp is not None and tick.timestamp < previous_timestamp:
            self.metrics.increment("pricing_out_of_order_total")
        self.metrics.increment("pricing_ticks_total")
        self.metrics.gauge("pricing_last_tick_timestamp_ms", tick.timestamp)
        return quote

    def quotes(self, symbols: set[str] | None = None) -> list[Quote]:
        output = [
            quote
            for symbol, window in self._windows.items()
            if (symbols is None or symbol in symbols) and (quote := window.quote()) is not None
        ]
        return sorted(output, key=lambda quote: quote.symbol)

    def export_state(self) -> dict[str, list[Tick]]:
        return {symbol: window.export_ticks() for symbol, window in self._windows.items()}
