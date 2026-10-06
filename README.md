# Real-Time Pricing Engine - Python / FastAPI

A low-latency Python service that authenticates with the LiveFXHub WebSocket feed, computes its own rolling 24-hour statistics, persists state across restarts, and distributes compact updates through FastAPI WebSockets.

The engine deliberately ignores every high, low, and percentage value supplied by the upstream feed.

## Technology stack

- Python 3.12
- FastAPI and Uvicorn
- `websockets` for authenticated LiveFXHub ingestion
- FastAPI WebSockets for client subscriptions
- MessagePack and compact JSON output
- `asyncio` for non-blocking ingestion, persistence, and fan-out
- JSON snapshot plus write-ahead log for restart recovery
- pytest for unit and WebSocket integration tests
- Docker and Docker Compose

## Run with Docker

Docker Desktop must be running. Credentials are loaded automatically from the git-ignored `.env` file.

```powershell
docker compose up --build -d
docker compose ps
docker compose logs -f pricing-engine
```

Open:

- `http://localhost:8080/` - service information
- `http://localhost:8080/docs` - interactive FastAPI API documentation
- `http://localhost:8080/healthz` - liveness
- `http://localhost:8080/readyz` - live/restored quote readiness
- `http://localhost:8080/api/v1/prices` - current computed prices
- `http://localhost:8080/api/v1/prices?symbols=EURUSD,BTCUSD` - filtered prices
- `http://localhost:8080/metrics` - Prometheus-format metrics
- `ws://localhost:8080/ws` - subscription WebSocket

Stop the service with:

```powershell
docker compose down
```

The named volume `pricing-data` stores the snapshot and WAL, so state survives container replacement.

## Local Python development

Create a Python 3.12 virtual environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

Run tests:

```powershell
python -m pytest -q --basetemp=tmp/pytest
```

Run the service locally:

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload --env-file .env
```

Run the benchmark:

```powershell
python -m scripts_py.benchmark
```

Receive one live downstream update:

```powershell
python -m scripts_py.client
```

For a credential-free demonstration, start the included fake upstream:

```powershell
python -m app.simulator
```

Then point the service to `ws://127.0.0.1:9090` with demo credentials.

## Downstream WebSocket

Connect to `/ws` and subscribe:

```json
{"action":"subscribe","symbols":["EURUSD","BTCUSD"],"encoding":"json"}
```

Use `"symbols":["*"]` for all instruments or `"encoding":"msgpack"` for binary data. The first application frame is a filtered snapshot; later frames are deltas.

## Calculation model

- `buy` and `sell` come from the latest event timestamp, not arrival order.
- The default statistical price is `(buy + sell) / 2`; `PRICE_BASIS` can select `buy` or `sell`.
- High and low are extrema over the active rolling 24-hour window.
- Percentage change is `(latest - earliest) / earliest * 100` inside that window.
- Ordered updates use monotonic queues with amortized O(1) extrema maintenance.
- In-window late events are inserted by time and rebuild only that symbol's extrema.
- Exact duplicates are suppressed across reconnects and recent restarts.
- The production feed currently sends `bid`/`ask` without a timestamp. Only its named market-price events use receipt time as the event-time fallback.

## Project layout

```text
app/ingestion/       authenticated upstream WebSocket client
app/processing/      parsing, deduplication, and rolling calculations
app/persistence/     asynchronous WAL and atomic snapshots
app/distribution/    FastAPI WebSocket client hub
app/main.py          FastAPI routes and application lifespan
tests_py/            unit and integration tests
scripts_py/          repeatable processing benchmark
docs/                architecture, protocol, and trade-offs
```

Additional documentation:

- [Architecture](docs/architecture.md)
- [WebSocket protocol](docs/protocol.md)
- [Design decisions](docs/design-decisions.md)
- [Challenges](docs/challenges.md)
