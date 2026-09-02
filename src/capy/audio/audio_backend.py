from collections.abc import Callable
from enum import StrEnum
from typing import Protocol


class EventType(StrEnum):
    MUSIC_END = "music_end"
    STATUS_PAUSED = "paused"
    STATUS_PLAYING = "playing"


class AudioBackend(Protocol):
    def init(self) -> None: ...

    def loop(self) -> None: ...

    def play(self, song: dict) -> None: ...

    def on_event(self, event_type: EventType, fn: Callable) -> None: ...
