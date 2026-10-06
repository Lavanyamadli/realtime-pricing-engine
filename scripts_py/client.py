from __future__ import annotations

import asyncio
import json
import os

from websockets.asyncio.client import connect

FIELDS = ("symbol", "buy", "sell", "high24h", "low24h", "change24h", "timestamp", "version")


async def main() -> None:
    url = os.getenv("PRICING_WS_URL", "ws://127.0.0.1:8080/ws")
    symbols = [value.strip().upper() for value in os.getenv("PRICING_SYMBOLS", "EURUSD,BTCUSD").split(",")]
    async with connect(url) as socket:
        hello = json.loads(await socket.recv())
        print(json.dumps(hello, indent=2))
        await socket.send(json.dumps({"action": "subscribe", "symbols": symbols, "encoding": "json"}))
        while True:
            message = json.loads(await socket.recv())
            if message.get("t") == "u":
                print(json.dumps(dict(zip(FIELDS, message["q"], strict=True)), indent=2))
                return
            print(json.dumps(message, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
