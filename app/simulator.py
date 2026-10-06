from __future__ import annotations

import asyncio
import json
import os
import random

from websockets.asyncio.server import serve

from app.config import SYMBOLS


async def handler(socket: object) -> None:
    prices = {symbol: 1 + index / 10 for index, symbol in enumerate(SYMBOLS)}
    symbols: list[str] = []
    async for raw in socket:  # type: ignore[attr-defined]
        message = json.loads(raw)
        if message.get("action") == "auth":
            await socket.send(json.dumps({"event": "authenticated", "success": True}))  # type: ignore[attr-defined]
        elif message.get("action") == "subscribeMarketPrice":
            symbols = message.get("symbols", list(SYMBOLS))
            while True:
                for symbol in symbols:
                    price = prices.get(symbol, 1) * (1 + random.uniform(-0.0001, 0.0001))
                    prices[symbol] = price
                    await socket.send(  # type: ignore[attr-defined]
                        json.dumps(
                            {
                                "event": "marketPriceUpdate",
                                "symbol": symbol,
                                "bid": price - 0.00005,
                                "ask": price + 0.00005,
                                "high": 999999,
                                "low": 0,
                                "percentage": 42,
                            }
                        )
                    )
                await asyncio.sleep(0.1)


async def main() -> None:
    port = int(os.getenv("SIMULATOR_PORT", "9090"))
    async with serve(handler, "127.0.0.1", port):
        print(f"simulator listening at ws://127.0.0.1:{port}")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
