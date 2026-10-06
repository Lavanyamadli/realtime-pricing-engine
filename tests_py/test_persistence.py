from pathlib import Path

from app.models import Tick
from app.persistence.store import StateStore


async def test_restores_snapshot_and_subsequent_wal(tmp_path: Path) -> None:
    store = StateStore(str(tmp_path))
    await store.start()
    first = Tick("EURUSD", 1, 2, 1, 1)
    second = Tick("EURUSD", 2, 3, 2, 2)
    store.record(first)
    await store.compact({"EURUSD": [first]})
    store.record(second)
    await store.close()

    _, restored = await StateStore(str(tmp_path)).load()
    assert restored["EURUSD"] == [first, second]
