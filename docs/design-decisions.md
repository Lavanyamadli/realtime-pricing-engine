# Design decisions and trade-offs

## Event time instead of arrival time

Rolling statistics use the feed timestamp. Arrival-time windows give incorrect results after a reconnect or network reordering. A new tick older than the current 24-hour watermark is dropped; an in-window late tick is incorporated without replacing the latest buy and sell.

The observed LiveFXHub production envelope differs from the assignment schema: `marketPriceSnapshot` and `marketPriceUpdate` carry `bid` and `ask` but no timestamp. For only those explicitly named messages, the adapter uses receipt time as the best available event time. If the provider adds a timestamp, it takes precedence automatically.

## Mid-price as default

The assignment does not define whether 24-hour fields use bid, ask, or mid. Mid-price is neutral and is the default. `PRICE_BASIS` makes the choice explicit and operationally changeable.

## Monotonic queues with a slow exceptional path

Max/min monotonic queues give amortized O(1) ordered updates and eviction. Supporting arbitrary event-time insertion in the same structure adds substantial complexity. Since late events are exceptional, the implementation uses binary insertion and an O(n) rebuild only for that symbol when one occurs.

## Local WAL and snapshot

The local persistence implementation has no external infrastructure, makes `docker compose up` sufficient, and recovers process/container restarts. It does not provide multi-machine replication. Production scale can replace `StateStore` behind its boundary with Kafka/Redpanda and a replicated state store.

## Delta protocol

Clients receive one full filtered snapshot on subscribe and thereafter one compact update per changed symbol. This is both smaller and cheaper than broadcasting all 61 instruments every tick. Positional arrays trade some readability for wire efficiency; the hello frame and protocol document supply the schema.

## Backpressure policy

Market data becomes less useful when queued. Rather than accumulate stale prices and eventually exhaust memory, the server disconnects a slow client with retryable close code 1013. The client can reconnect and receive a fresh snapshot.
