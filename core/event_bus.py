"""In-process pub/sub event bus singleton."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Callable


class EventBus:
    _instance: EventBus | None = None

    def __new__(cls) -> EventBus:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._subscribers: dict[type, list[Callable]] = defaultdict(list)
            cls._instance._async_queues: dict[type, list[asyncio.Queue]] = defaultdict(list)
        return cls._instance

    def subscribe(self, event_type: type, handler: Callable) -> None:
        self._subscribers[event_type].append(handler)

    def subscribe_async(self, event_type: type, queue: asyncio.Queue) -> None:
        self._async_queues[event_type].append(queue)

    def publish(self, event: Any) -> None:
        event_type = type(event)
        for handler in self._subscribers.get(event_type, []):
            try:
                handler(event)
            except Exception:
                pass
        for q in self._async_queues.get(event_type, []):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def clear(self) -> None:
        self._subscribers.clear()
        self._async_queues.clear()

    @classmethod
    def reset(cls) -> None:
        cls._instance = None
