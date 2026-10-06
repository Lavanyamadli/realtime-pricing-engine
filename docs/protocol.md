# Downstream WebSocket protocol

Connect to `GET /ws`. Protocol version 1 uses JSON client control messages. Server data messages may be JSON text or MessagePack binary.

## Subscribe

```json
{"action":"subscribe","symbols":["EURUSD","XAUUSD"],"encoding":"msgpack"}
```

`symbols` accepts configured symbols or the wildcard `*`. `encoding` is optional and is `json` or `msgpack`. A successful subscription produces a JSON acknowledgement followed by a snapshot.

## Unsubscribe

```json
{"action":"unsubscribe","symbols":["EURUSD"]}
```

## Data frames

Snapshot:

```json
{"t":"s","q":[["EURUSD",1.1,1.1001,1.12,1.08,0.45,1700000000000,20]]}
```

Delta:

```json
{"t":"u","q":["EURUSD",1.1,1.1001,1.12,1.08,0.45,1700000000000,21]}
```

The quote array positions are fixed:

| Index | Field | Meaning |
|---:|---|---|
| 0 | symbol | Instrument identifier |
| 1 | buy | Latest event-time buy |
| 2 | sell | Latest event-time sell |
| 3 | high24h | Computed rolling high |
| 4 | low24h | Computed rolling low |
| 5 | change24h | Computed rolling percent change |
| 6 | timestamp | Latest event time in Unix milliseconds |
| 7 | version | Per-symbol accepted-update counter |

The compact positional schema avoids repeating field names for every quote. MessagePack reduces numeric and structural overhead further; WebSocket per-message compression is also negotiated.

## Limits and close codes

- Client messages: maximum 16 KiB and 20 messages per second.
- Application data frames: less than 10,000 bytes.
- Close `1008`: control-message rate limit.
- Close `1009`: generated payload unexpectedly exceeded the size contract.
- Close `1013`: downstream client failed to drain its buffer.
