# Challenges faced

## Exact rolling results under out-of-order delivery

An arrival-ordered queue is fast but wrong when old ticks arrive late. The solution tracks event time per symbol: ordered traffic uses monotonic extrema queues, while a late but still relevant event is inserted into the sorted window and rebuilds only that symbol's extrema. Too-old events are rejected.

## Restart safety without adding infrastructure

Snapshots alone lose everything since the last snapshot, while synchronous persistence would harm the 50 ms latency target. The engine therefore appends accepted ticks to an ordered asynchronous WAL and atomically replaces periodic snapshots. Compaction is serialized with WAL writes, preventing a truncate/write race.

## Staying below 10 KB

Verbose JSON keys repeated for all 61 instruments can waste much of the budget. Subscription filtering, snapshots followed by deltas, positional quote arrays, optional MessagePack, and per-message deflate keep normal frames well below the limit. The server measures every generated application frame and fails closed if the contract is violated.

## Isolating slow consumers

One client that stops reading must not delay upstream processing or other clients. Every socket is checked independently for buffered bytes; a lagging client is disconnected and can recover from a fresh snapshot.

## Unknown upstream response envelope

The assignment specifies the request shape but not the exact response envelope. Authentication handling accepts common explicit success forms, price parsing accepts direct, `data`, or `prices` batches, and malformed records are counted and ignored. The parser is deliberately narrow about the four trusted input fields.
