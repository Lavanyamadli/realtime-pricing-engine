import time

from app.metrics import Metrics
from app.models import Tick
from app.processing.engine import PricingEngine


def test_deduplicates_identical_ticks() -> None:
    metrics = Metrics()
    engine = PricingEngine(86_400_000, "mid", 60_000, metrics)
    tick = Tick("EURUSD", 1, 1.2, 1000, 2000)
    assert engine.process(tick) is not None
    assert engine.process(Tick("EURUSD", 1, 1.2, 1000, 2001)) is None
    assert "pricing_duplicates_total 1" in metrics.render()


def test_restored_ticks_retain_recent_duplicate_protection() -> None:
    now = int(time.time() * 1000)
    tick = Tick("EURUSD", 1, 1.2, now, now)
    engine = PricingEngine(86_400_000, "mid", 60_000, Metrics())
    engine.restore({"EURUSD": [tick]})
    assert engine.process(Tick("EURUSD", 1, 1.2, now, now + 1)) is None
