from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

from app.models import Tick

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _Record:
    tick: Tick


@dataclass(slots=True)
class _Compact:
    serialized: str
    completed: asyncio.Future[None]


class StateStore:
    def __init__(self, directory: str) -> None:
        self.directory = Path(directory)
        self.snapshot_path = self.directory / "state.snapshot.json"
        self.wal_path = self.directory / "ticks.wal.jsonl"
        self._queue: asyncio.Queue[_Record | _Compact | None] = asyncio.Queue()
        self._worker: asyncio.Task[None] | None = None
        self._failure: Exception | None = None

    async def load(self) -> tuple[int, dict[str, list[Tick]]]:
        return await asyncio.to_thread(self._load_sync)

    def _load_sync(self) -> tuple[int, dict[str, list[Tick]]]:
        self.directory.mkdir(parents=True, exist_ok=True)
        saved_at = 0
        symbols: dict[str, list[Tick]] = {}
        if self.snapshot_path.exists():
            state = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
            if state.get("version") != 1 or not isinstance(state.get("symbols"), dict):
                raise ValueError("unsupported state snapshot")
            saved_at = int(state.get("saved_at", state.get("savedAt", 0)))
            symbols = {
                symbol: [Tick.from_dict(item) for item in ticks]
                for symbol, ticks in state["symbols"].items()
            }
        if self.wal_path.exists():
            lines = [line for line in self.wal_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            for index, line in enumerate(lines):
                try:
                    tick = Tick.from_dict(json.loads(line))
                except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
                    if index != len(lines) - 1:
                        raise ValueError(f"corrupt WAL record at line {index + 1}") from error
                    continue
                symbols.setdefault(tick.symbol, []).append(tick)
        return saved_at, symbols

    async def start(self) -> None:
        if self._worker is None:
            self._worker = asyncio.create_task(self._run(), name="state-store")

    def record(self, tick: Tick) -> None:
        if self._failure is not None:
            raise RuntimeError("state store worker failed") from self._failure
        self._queue.put_nowait(_Record(tick))

    async def compact(self, symbols: dict[str, list[Tick]]) -> None:
        if self._failure is not None:
            raise RuntimeError("state store worker failed") from self._failure
        loop = asyncio.get_running_loop()
        completed: asyncio.Future[None] = loop.create_future()
        state = {
            "version": 1,
            "saved_at": int(time.time() * 1000),
            "symbols": {symbol: [tick.to_dict() for tick in ticks] for symbol, ticks in symbols.items()},
        }
        await self._queue.put(_Compact(json.dumps(state, separators=(",", ":")), completed))
        await completed

    async def close(self) -> None:
        if self._worker is None:
            return
        await self._queue.put(None)
        await self._worker
        self._worker = None

    async def _run(self) -> None:
        while True:
            operation = await self._queue.get()
            try:
                if operation is None:
                    return
                if isinstance(operation, _Record):
                    await asyncio.to_thread(self._append_sync, operation.tick)
                else:
                    await asyncio.to_thread(self._compact_sync, operation.serialized)
                    operation.completed.set_result(None)
            except Exception as error:
                self._failure = error
                logger.exception("state store operation failed")
                if isinstance(operation, _Compact) and not operation.completed.done():
                    operation.completed.set_exception(error)
                while not self._queue.empty():
                    pending = self._queue.get_nowait()
                    if isinstance(pending, _Compact) and not pending.completed.done():
                        pending.completed.set_exception(error)
                    self._queue.task_done()
                return
            finally:
                self._queue.task_done()

    def _append_sync(self, tick: Tick) -> None:
        with self.wal_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(tick.to_dict(), separators=(",", ":")) + "\n")

    def _compact_sync(self, serialized: str) -> None:
        temporary = self.snapshot_path.with_suffix(".json.tmp")
        temporary.write_text(serialized, encoding="utf-8")
        os.replace(temporary, self.snapshot_path)
        self.wal_path.write_text("", encoding="utf-8")
