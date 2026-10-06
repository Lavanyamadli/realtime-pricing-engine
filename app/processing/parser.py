from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Any

from app.models import Tick


def _timestamp_ms(value: object) -> int | None:
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            try:
                return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)
            except ValueError:
                return None
    if not isinstance(value, (int, float)) or not isfinite(value):
        return None
    if value < 10_000_000_000:
        return int(value * 1000)
    if value > 10_000_000_000_000:
        return int(value / 1000)
    return int(value)


def parse_ticks(payload: object, received_at: int) -> list[Tick]:
    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, dict) and isinstance(payload.get("data"), list):
        candidates = payload["data"]
    elif isinstance(payload, dict) and isinstance(payload.get("prices"), list):
        candidates = payload["prices"]
    else:
        candidates = [payload]

    output: list[Tick] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        symbol_value = candidate.get("symbol")
        if not isinstance(symbol_value, str):
            continue
        try:
            buy = float(candidate.get("buy", candidate.get("bid")))
            sell = float(candidate.get("sell", candidate.get("ask")))
        except (TypeError, ValueError):
            continue
        market_event = candidate.get("event") in {"marketPriceSnapshot", "marketPriceUpdate"}
        timestamp = received_at if candidate.get("timestamp") is None and market_event else _timestamp_ms(candidate.get("timestamp"))
        if not isfinite(buy) or not isfinite(sell) or buy <= 0 or sell <= 0 or timestamp is None:
            continue
        output.append(
            Tick(
                symbol=symbol_value.upper(),
                buy=buy,
                sell=sell,
                timestamp=timestamp,
                received_at=received_at,
            )
        )
    return output
