from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field

import msgpack
from fastapi import WebSocket, WebSocketDisconnect

from app.metrics import Metrics
from app.models import OutputEncoding, Quote, Tick
from app.processing.engine import PricingEngine


@dataclass(slots=True)
class ClientState:
    socket: WebSocket
    encoding: OutputEncoding
    symbols: set[str] = field(default_factory=set)
    all_symbols: bool = False
    message_count: int = 0
    rate_window_started_at: int = field(default_factory=lambda: int(time.time() * 1000))
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class DistributionHub:
    def __init__(
        self,
        engine: PricingEngine,
        metrics: Metrics,
        allowed_symbols: set[str],
        default_encoding: OutputEncoding,
    ) -> None:
        self.engine = engine
        self.metrics = metrics
        self.allowed_symbols = allowed_symbols
        self.default_encoding = default_encoding
        self._clients: dict[int, ClientState] = {}
        self._clients_lock = asyncio.Lock()

    async def handle(self, socket: WebSocket) -> None:
        await socket.accept()
        state = ClientState(socket=socket, encoding=self.default_encoding)
        key = id(socket)
        async with self._clients_lock:
            self._clients[key] = state
            self.metrics.gauge("pricing_downstream_clients", len(self._clients))
        await socket.send_json(
            {
                "type": "hello",
                "protocol": 1,
                "fields": ["symbol", "buy", "sell", "high24h", "low24h", "change24h", "timestamp", "version"],
            }
        )
        try:
            while True:
                raw = await socket.receive_text()
                await self._handle_control(state, raw)
        except WebSocketDisconnect:
            pass
        finally:
            async with self._clients_lock:
                self._clients.pop(key, None)
                self.metrics.gauge("pricing_downstream_clients", len(self._clients))

    async def broadcast(self, quote: Quote, tick: Tick) -> None:
        async with self._clients_lock:
            clients = list(self._clients.values())
        targets = [state for state in clients if state.all_symbols or quote.symbol in state.symbols]
        if not targets:
            return
        await asyncio.gather(*(self._send_data(state, {"t": "u", "q": quote.compact()}) for state in targets))
        self.metrics.increment("pricing_updates_sent_total", len(targets))
        self.metrics.gauge("pricing_processing_latency_ms", max(0, int(time.time() * 1000) - tick.received_at))

    async def _handle_control(self, state: ClientState, raw: str) -> None:
        now = int(time.time() * 1000)
        if now - state.rate_window_started_at >= 1000:
            state.rate_window_started_at = now
            state.message_count = 0
        state.message_count += 1
        if state.message_count > 20:
            await state.socket.close(code=1008, reason="rate limit exceeded")
            return
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            await state.socket.send_json({"type": "error", "code": "INVALID_JSON"})
            return
        if not isinstance(message, dict):
            await state.socket.send_json({"type": "error", "code": "INVALID_MESSAGE"})
            return
        if message.get("action") == "ping":
            await state.socket.send_json({"type": "pong", "timestamp": now})
            return
        action = message.get("action")
        if action not in {"subscribe", "unsubscribe"}:
            await state.socket.send_json({"type": "error", "code": "INVALID_ACTION"})
            return
        encoding = message.get("encoding")
        if encoding in {"json", "msgpack"}:
            state.encoding = encoding
        requested = message.get("symbols", [])
        normalized = [value.upper() for value in requested if isinstance(value, str)] if isinstance(requested, list) else []
        if action == "unsubscribe":
            for symbol in normalized:
                state.symbols.discard(symbol)
            if "*" in normalized:
                state.all_symbols = False
            await state.socket.send_json({"type": "subscribed", "symbols": ["*"] if state.all_symbols else sorted(state.symbols)})
            return
        invalid = [symbol for symbol in normalized if symbol != "*" and symbol not in self.allowed_symbols]
        if invalid:
            await state.socket.send_json({"type": "error", "code": "UNKNOWN_SYMBOL", "symbols": invalid})
            return
        if "*" in normalized:
            state.all_symbols = True
        else:
            state.symbols.update(normalized)
        await state.socket.send_json(
            {
                "type": "subscribed",
                "symbols": ["*"] if state.all_symbols else sorted(state.symbols),
                "encoding": state.encoding,
            }
        )
        selected = None if state.all_symbols else state.symbols
        await self._send_data(state, {"t": "s", "q": [quote.compact() for quote in self.engine.quotes(selected)]})

    async def _send_data(self, state: ClientState, value: object) -> None:
        if state.encoding == "msgpack":
            payload = msgpack.packb(value, use_bin_type=True)
        else:
            payload = json.dumps(value, separators=(",", ":"))
        size = len(payload.encode()) if isinstance(payload, str) else len(payload)
        if size >= 10_000:
            self.metrics.increment("pricing_oversized_payloads_total")
            await state.socket.close(code=1009, reason="payload exceeds 10KB")
            return
        try:
            async with state.send_lock:
                if isinstance(payload, str):
                    await asyncio.wait_for(state.socket.send_text(payload), timeout=0.05)
                else:
                    await asyncio.wait_for(state.socket.send_bytes(payload), timeout=0.05)
            self.metrics.gauge("pricing_last_payload_bytes", size)
        except (TimeoutError, RuntimeError):
            self.metrics.increment("pricing_slow_clients_total")
            try:
                await state.socket.close(code=1013, reason="client too slow")
            except RuntimeError:
                pass
