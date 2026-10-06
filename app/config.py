from __future__ import annotations

import os
from dataclasses import dataclass

from app.models import OutputEncoding, PriceBasis

SYMBOLS: tuple[str, ...] = (
    "AUDUSD", "AUDCAD", "AUDCHF", "AUDJPY", "AUDNZD", "AUDSGD", "CADCHF", "CADJPY",
    "CHFJPY", "CHFSGD", "EURAUD", "EURCAD", "EURCHF", "EURGBP", "EURJPY", "EURNZD",
    "EURUSD", "GBPAUD", "GBPCAD", "GBPCHF", "GBPJPY", "GBPNZD", "GBPUSD", "NZDCAD",
    "NZDCHF", "NZDJPY", "NZDUSD", "USDCAD", "USDCHF", "USDCNH", "USDJPY", "USDMXN",
    "USDNOK", "USDPLN", "USDSEK", "USDSGD", "USDTRY", "USDZAR", "EURTRY", "GBPTRY",
    "NOKJPY", "SEKJPY", "SGDJPY", "ZARJPY", "XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD",
    "BNBUSD", "SOLUSD", "XRPUSD", "ADAUSD", "DOGUSD", "DOTUSD", "LTCUSD", "BCHUSD",
    "XLMUSD", "TRXUSD", "UNIUSD", "FILUSD", "AVXUSD",
)


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    value = int(raw)
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    upstream_url: str = "wss://v3-prod.livefxhub.com/ws/algo"
    api_key: str | None = None
    api_secret: str | None = None
    data_dir: str = "./data"
    output_encoding: OutputEncoding = "json"
    price_basis: PriceBasis = "mid"
    snapshot_interval_ms: int = 30_000
    max_client_buffer_bytes: int = 1_048_576
    window_ms: int = 24 * 60 * 60 * 1000
    dedupe_ttl_ms: int = 60_000

    @classmethod
    def from_env(cls) -> Settings:
        encoding = os.getenv("OUTPUT_ENCODING", "json")
        basis = os.getenv("PRICE_BASIS", "mid")
        if encoding not in {"json", "msgpack"}:
            raise ValueError("OUTPUT_ENCODING must be json or msgpack")
        if basis not in {"mid", "buy", "sell"}:
            raise ValueError("PRICE_BASIS must be mid, buy, or sell")
        return cls(
            upstream_url=os.getenv("UPSTREAM_URL", "wss://v3-prod.livefxhub.com/ws/algo"),
            api_key=os.getenv("API_KEY") or None,
            api_secret=os.getenv("API_SECRET") or None,
            data_dir=os.getenv("DATA_DIR", "./data"),
            output_encoding=encoding,  # type: ignore[arg-type]
            price_basis=basis,  # type: ignore[arg-type]
            snapshot_interval_ms=_positive_int("SNAPSHOT_INTERVAL_MS", 30_000),
            max_client_buffer_bytes=_positive_int("MAX_CLIENT_BUFFER_BYTES", 1_048_576),
            dedupe_ttl_ms=_positive_int("DEDUPE_TTL_MS", 60_000),
        )
