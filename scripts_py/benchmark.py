from __future__ import annotations

import json
import os
import time

from app.metrics import Metrics
from app.models import Tick
from app.processing.engine import PricingEngine

total = int(os.getenv("BENCHMARK_TICKS", "100000"))
engine = PricingEngine(86_400_000, "mid", 60_000, Metrics())
latencies: list[float] = []
started = time.perf_counter()
for index in range(total):
    before = time.perf_counter()
    engine.process(
        Tick(
            symbol=f"S{index % 61}",
            buy=100 + (index % 100) / 10_000,
            sell=100.01 + (index % 100) / 10_000,
            timestamp=1_700_000_000_000 + index,
            received_at=int(time.time() * 1000),
        )
    )
    latencies.append((time.perf_counter() - before) * 1000)
elapsed_ms = (time.perf_counter() - started) * 1000
latencies.sort()


def percentile(value: float) -> float:
    return latencies[min(len(latencies) - 1, int(len(latencies) * value))]


print(
    json.dumps(
        {
            "ticks": total,
            "elapsedMs": round(elapsed_ms, 2),
            "ticksPerSecond": round(total / (elapsed_ms / 1000)),
            "p50ProcessingMs": round(percentile(0.50), 4),
            "p95ProcessingMs": round(percentile(0.95), 4),
            "p99ProcessingMs": round(percentile(0.99), 4),
        },
        indent=2,
    )
)
