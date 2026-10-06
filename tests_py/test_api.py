import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import SYMBOLS, Settings
from app.main import create_app
from app.models import Tick


def _write_snapshot(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    now = int(time.time() * 1000)
    state = {
        "version": 1,
        "saved_at": now,
        "symbols": {
            symbol: [
                Tick(symbol, 1 + index / 10, 1.001 + index / 10, now, now).to_dict()
            ]
            for index, symbol in enumerate(SYMBOLS)
        },
    }
    (directory / "state.snapshot.json").write_text(json.dumps(state), encoding="utf-8")


def test_health_prices_and_compact_websocket_snapshot(tmp_path: Path) -> None:
    _write_snapshot(tmp_path)
    app = create_app(Settings(data_dir=str(tmp_path)))
    with TestClient(app) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
        assert client.get("/readyz").json() == {"status": "ready"}
        price_response = client.get("/api/v1/prices", params={"symbols": "EURUSD"}).json()
        assert price_response["count"] == 1
        with client.websocket_connect("/ws") as socket:
            assert socket.receive_json()["type"] == "hello"
            socket.send_json({"action": "subscribe", "symbols": ["*"]})
            assert socket.receive_json()["type"] == "subscribed"
            raw = socket.receive_text()
            snapshot = json.loads(raw)
            assert snapshot["t"] == "s"
            assert len(snapshot["q"]) == len(SYMBOLS)
            assert len(raw.encode()) < 10_000
