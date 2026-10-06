from app.processing.parser import parse_ticks


def test_parses_assignment_batch_and_ignores_derived_fields() -> None:
    ticks = parse_ticks(
        {
            "data": [
                {
                    "symbol": "eurusd",
                    "buy": "1.1",
                    "sell": 1.2,
                    "timestamp": 1_700_000_000,
                    "low_24h": -500,
                    "high_24h": 500,
                    "change_24h": 999,
                }
            ]
        },
        123,
    )
    assert len(ticks) == 1
    assert ticks[0].symbol == "EURUSD"
    assert ticks[0].buy == 1.1
    assert ticks[0].sell == 1.2
    assert ticks[0].timestamp == 1_700_000_000_000


def test_adapts_live_bid_ask_envelope() -> None:
    ticks = parse_ticks(
        {
            "event": "marketPriceUpdate",
            "symbol": "EURUSD",
            "bid": 1.12631,
            "ask": 1.12647,
            "high": 999,
            "low": 0,
            "percentage": 42,
        },
        1_800_000_000_123,
    )
    assert len(ticks) == 1
    assert ticks[0].buy == 1.12631
    assert ticks[0].sell == 1.12647
    assert ticks[0].timestamp == 1_800_000_000_123


def test_drops_malformed_prices() -> None:
    assert parse_ticks({"symbol": "EURUSD", "buy": -1, "sell": 2, "timestamp": 10}, 10) == []
    assert parse_ticks({"symbol": "EURUSD", "buy": 1, "sell": "bad", "timestamp": 10}, 10) == []
