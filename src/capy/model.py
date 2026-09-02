from dataclasses import dataclass, field


@dataclass
class PlayingStatus:
    duration: int = 0
    position: int = 0
    state: str = "stopped"


@dataclass
class AlbumPlaylist:
    albums: list[dict] = field(default_factory=list)
