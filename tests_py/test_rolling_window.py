from app.models import Tick
from app.processing.rolling_window import RollingWindow

HOUR = 60 * 60 * 1000


def tick(timestamp: int, price: float) -> Tick:
    return Tick("EURUSD", price - 0.0001, price + 0.0001, timestamp, timestamp)


def test_computes_high_low_and_change() -> None:
    window = RollingWindow("EURUSD", 24 * HOUR, "mid")
    window.add(tick(0, 100))
    window.add(tick(HOUR, 105))
    quote = window.add(tick(2 * HOUR, 90))
    assert quote is not None
    assert quote.high_24h == 105
    assert quote.low_24h == 90
    assert quote.change_24h == -10


def test_evicts_outside_24_hour_window() -> None:
    window = RollingWindow("EURUSD", 24 * HOUR, "mid")
    window.add(tick(0, 200))
    window.add(tick(HOUR, 100))
    quote = window.add(tick(25 * HOUR, 110))
    assert quote is not None
    assert quote.high_24h == 110
    assert quote.low_24h == 100
    assert quote.change_24h == 10
    assert len(window.export_ticks()) == 2


def test_handles_in_window_out_of_order_tick() -> None:
    window = RollingWindow("EURUSD", 24 * HOUR, "mid")
    window.add(tick(10 * HOUR, 100))
    window.add(tick(12 * HOUR, 110))
    quote = window.add(tick(11 * HOUR, 80))
    assert quote is not None
    assert quote.timestamp == 12 * HOUR
    assert quote.buy == 109.9999
    assert quote.high_24h == 110
    assert quote.low_24h == 80


def test_rejects_too_old_tick() -> None:
    window = RollingWindow("EURUSD", 24 * HOUR, "mid")
    window.add(tick(30 * HOUR, 100))
    assert window.add(tick(5 * HOUR, 1)) is None
    assert len(window.export_ticks()) == 1
