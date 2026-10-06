from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, Request, WebSocket
from fastapi.responses import JSONResponse, PlainTextResponse

from app.config import Settings
from app.logging_config import configure_logging
from app.runtime import Runtime

configure_logging()


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        runtime = Runtime(resolved)
        application.state.runtime = runtime
        await runtime.start()
        try:
            yield
        finally:
            await runtime.stop()

    application = FastAPI(
        title="Real-Time Pricing Engine",
        version="1.0.0",
        description="LiveFXHub ingestion with computed rolling 24-hour market statistics.",
        lifespan=lifespan,
    )

    @application.get("/", response_class=JSONResponse)
    async def root() -> dict[str, object]:
        return {
            "service": "real-time-pricing-engine",
            "runtime": "Python / FastAPI",
            "websocket": "/ws",
            "health": "/healthz",
            "readiness": "/readyz",
            "metrics": "/metrics",
            "api_docs": "/docs",
        }

    @application.get("/healthz", response_class=JSONResponse)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/readyz", response_class=JSONResponse)
    async def readiness(request: Request) -> JSONResponse:
        ready = request.app.state.runtime.ready
        return JSONResponse({"status": "ready" if ready else "not_ready"}, status_code=200 if ready else 503)

    @application.get("/metrics", response_class=PlainTextResponse)
    async def metrics(request: Request) -> PlainTextResponse:
        return PlainTextResponse(request.app.state.runtime.metrics.render(), media_type="text/plain; version=0.0.4")

    @application.get("/api/v1/prices", response_class=JSONResponse)
    async def prices(request: Request, symbols: str | None = Query(default=None)) -> dict[str, object]:
        selected = {symbol.strip().upper() for symbol in symbols.split(",")} if symbols else None
        quotes = request.app.state.runtime.engine.quotes(selected)
        return {"count": len(quotes), "quotes": [quote.to_dict() for quote in quotes]}

    @application.websocket("/ws")
    async def websocket_endpoint(socket: WebSocket) -> None:
        await socket.app.state.runtime.hub.handle(socket)

    return application


app = create_app()
