from __future__ import annotations

import asyncio
import logging

from app.config import SYMBOLS, Settings
from app.distribution.hub import DistributionHub
from app.ingestion.upstream import UpstreamClient
from app.metrics import Metrics
from app.models import Tick
from app.persistence.store import StateStore
from app.processing.engine import PricingEngine

logger = logging.getLogger(__name__)


class Runtime:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.metrics = Metrics()
        self.store = StateStore(settings.data_dir)
        self.engine = PricingEngine(settings.window_ms, settings.price_basis, settings.dedupe_ttl_ms, self.metrics)
        self.hub = DistributionHub(
            engine=self.engine,
            metrics=self.metrics,
            allowed_symbols=set(SYMBOLS),
            default_encoding=settings.output_encoding,
        )
        self.upstream: UpstreamClient | None = None
        self.received_live_tick = False
        self._snapshot_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        saved_at, symbols = await self.store.load()
        self.engine.restore(symbols)
        await self.store.start()
        logger.info("state restored", extra={"fields": {"symbols": len(symbols), "saved_at": saved_at or None}})
        self._snapshot_task = asyncio.create_task(self._snapshot_loop(), name="snapshot-loop")
        if self.settings.api_key and self.settings.api_secret:
            self.upstream = UpstreamClient(
                url=self.settings.upstream_url,
                api_key=self.settings.api_key,
                api_secret=self.settings.api_secret,
                symbols=SYMBOLS,
                metrics=self.metrics,
                on_tick=self.ingest_tick,
            )
            self.upstream.start()
        else:
            logger.warning("API credentials are absent; live ingestion is disabled")

    async def stop(self) -> None:
        if self.upstream:
            await self.upstream.stop()
        if self._snapshot_task:
            self._snapshot_task.cancel()
            try:
                await self._snapshot_task
            except asyncio.CancelledError:
                pass
        await self.store.compact(self.engine.export_state())
        await self.store.close()

    async def ingest_tick(self, tick: Tick) -> None:
        quote = self.engine.process(tick)
        if quote is None:
            return
        self.received_live_tick = True
        self.store.record(tick)
        await self.hub.broadcast(quote, tick)

    @property
    def ready(self) -> bool:
        return self.received_live_tick or bool(self.engine.quotes())

    async def _snapshot_loop(self) -> None:
        while True:
            await asyncio.sleep(self.settings.snapshot_interval_ms / 1000)
            try:
                await self.store.compact(self.engine.export_state())
            except Exception:
                logger.exception("state compaction failed")
