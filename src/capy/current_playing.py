from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, ProgressBar

from capy.albumart import AlbumArt
from capy.model import PlayingStatus
from capy.utils import format_time


class CurrentPlaying(Widget):
    song: reactive[dict] = reactive({}, recompose=True)
    status: reactive[PlayingStatus] = reactive(PlayingStatus)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.albumart = AlbumArt("")
        self.lbltitle = TitleTrack()
        self.artist = Label("No artist", classes="artist")
        self.album = Label("No album", classes="album")

    def watch_song(self, old, new) -> None:
        self.albumart.aid = new.get("coverArt", "")
        self.lbltitle.song = new
        self.artist.update(new.get("artist", "No artist"))
        self.album.update(new.get("album", "No album"))
        self.display = self.song != {}

    def watch_status(self, old, new) -> None:
        self.lbltitle.status = new
        self.lbltitle.mutate_reactive(TitleTrack.status)

    def compose(self) -> ComposeResult:

        yield self.albumart
        yield self.lbltitle
        yield Label("Artist", classes="muted")
        yield self.artist
        yield Label("Album", classes="muted")
        yield self.album
        yield ProgressTracker().data_bind(CurrentPlaying.status)


class TitleTrack(Widget):
    status: reactive[PlayingStatus] = reactive(PlayingStatus(), recompose=True)
    song: reactive[dict] = reactive({}, recompose=True)

    def compose(self) -> ComposeResult:
        if self.status.state == "playing":
            yield Label(" ", classes="icon")
        if self.status.state == "paused":
            yield Label(" ", classes="icon")
        yield Label(self.song.get("title", "No title"), classes="title")
        if self.status.state == "paused":
            yield Label("\\[paused]", classes="status")


class ProgressTracker(Widget):
    status: reactive[PlayingStatus] = reactive(PlayingStatus(), recompose=False)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.position = Label("--:--")
        self.duration = Label("--:--")
        self.progress = ProgressBar(show_eta=False, show_percentage=False)

    def watch_status(self, old_value: PlayingStatus, new_value: PlayingStatus) -> None:
        self.position.update(format_time(new_value.position))
        self.duration.update(format_time(new_value.duration))

        self.progress.update(progress=self.status.position, total=self.status.duration)

    def compose(self) -> ComposeResult:
        yield self.progress
        yield self.position
        yield Label(" / ")
        yield self.duration
