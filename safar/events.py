"""Event bus — in-process pub/sub (NO external broker). Owner: mr.jarvis0.

Honest local stand-in for the readme §15 event bus (Kafka/Redis Streams). Live
signals — flight delays, weather alerts, closures — are published here and the
On-Trip Copilot (engine.copilot) subscribes. Same API shape as a real broker, so
swapping in Redis/Kafka later is a one-file change.
"""
from collections import defaultdict
from typing import Callable

_subs: dict[str, list[Callable]] = defaultdict(list)


def subscribe(topic: str, fn: Callable) -> None:
    _subs[topic].append(fn)


def publish(topic: str, payload: dict) -> list:
    """Fan out to subscribers; returns their (non-None) return values."""
    out = []
    for fn in _subs.get(topic, []):
        r = fn(payload)
        if r is not None:
            out.append(r)
    return out


def reset() -> None:
    _subs.clear()
