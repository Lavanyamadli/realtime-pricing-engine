from __future__ import annotations


class Metrics:
    def __init__(self) -> None:
        self._counters: dict[str, int] = {}
        self._gauges: dict[str, int | float] = {}

    def increment(self, name: str, amount: int = 1) -> None:
        self._counters[name] = self._counters.get(name, 0) + amount

    def gauge(self, name: str, value: int | float) -> None:
        self._gauges[name] = value

    def render(self) -> str:
        lines: list[str] = []
        for name, value in sorted(self._counters.items()):
            lines.extend((f"# TYPE {name} counter", f"{name} {value}"))
        for name, value in sorted(self._gauges.items()):
            lines.extend((f"# TYPE {name} gauge", f"{name} {value}"))
        return "\n".join(lines) + "\n"
