from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from collections.abc import Awaitable, Callable, Sequence

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from app.metrics import Metrics
from app.models import Tick
from app.processing.parser import parse_ticks

logger = logging.getLogger(__name__)


def _auth_succeeded(message: object) -> bool:
    if not isinstance(message, dict):
        return False
    event = str(message.get("event", "")).lower()
    status = str(message.get("status", "")).lower()
    return (
        message.get("authenticated") is True
        or (message.get("success") is True and event in {"", "authenticated", "auth"})
        or status in {"success", "ok", "authenticated"}
    )


def _auth_failed(message: object) -> bool:
    if not isinstance(message, dict):
        return False
    text = json.dumps(message).lower()
    failure_signal = (
        message.get("success") is False
        or str(message.get("status", "")).lower() in {"error", "failed"}
        or str(message.get("event", "")).lower() == "error"
    )
    return failure_signal and any(word in text for word in ("auth", "credential", "key", "session"))


class UpstreamClient:
    def __init__(
        self,
        url: str,
        api_key: str,
        api_secret: str,
        symbols: Sequence[str],
        metrics: Metrics,
        on_tick: Callable[[Tick], Awaitable[None]],
    ) -> None:
        self.url = url
        self.api_key = api_key
        self.api_secret = api_secret
        self.symbols = list(symbols)
        self.metrics = metrics
        self.on_tick = on_tick
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="upstream-client")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run(self) -> None:
        attempt = 0
        while True:
            try:
                async with connect(self.url, max_size=1024 * 1024, open_timeout=10, ping_interval=20) as socket:
                    attempt = 0
                    self.metrics.gauge("pricing_upstream_connected", 1)
                    await socket.send(json.dumps({"action": "auth", "api_key": self.api_key, "secret": self.api_secret}))
                    logger.info("upstream connected; authentication sent")
                    authenticated = False
                    async for raw in socket:
                        received_at = int(time.time() * 1000)
                        try:
                            message = json.loads(raw)
                        except (json.JSONDecodeError, TypeError):
                            self.metrics.increment("pricing_invalid_messages_total")
                            continue
                        if not authenticated:
                            if _auth_succeeded(message):
                                authenticated = True
                                await socket.send(json.dumps({"action": "subscribeMarketPrice", "symbols": self.symbols}))
                                logger.info(
                                    "upstream authenticated; market subscription sent",
                                    extra={"fields": {"symbols": len(self.symbols)}},
                                )
                            elif _auth_failed(message):
                                raise ConnectionError("upstream authentication failed")
                            continue
                        for tick in parse_ticks(message, received_at):
                            await self.on_tick(tick)
            except asyncio.CancelledError:
                raise
            except (ConnectionClosed, OSError, TimeoutError, ConnectionError) as error:
                self.metrics.gauge("pricing_upstream_connected", 0)
                attempt += 1
                self.metrics.increment("pricing_upstream_reconnects_total")
                cap = min(30.0, 0.5 * (2 ** min(attempt, 8)))
                delay = random.uniform(cap / 2, cap)
                logger.warning(
                    "upstream disconnected; reconnecting",
                    extra={"fields": {"error": str(error), "delay_seconds": round(delay, 2)}},
                )
                await asyncio.sleep(delay)
