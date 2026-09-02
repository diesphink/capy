from rich.spinner import Spinner
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import Click
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, Static

from capy.albumart import AlbumArt
from capy.model import AlbumPlaylist
from capy.utils import format_time


class PlaylistWidget(Widget):
    playlist: reactive[AlbumPlaylist] = reactive(AlbumPlaylist(), recompose=True)
    song: reactive[dict] = reactive({})

    def compose(self) -> ComposeResult:
        for index, album in enumerate(self.playlist.albums):
            yield PlaylistAlbumWidget(album).data_bind(PlaylistWidget.song)
        self.scroll_home(animate=False)


class PlaylistAlbumWidget(Widget):
    album: reactive[dict] = reactive(dict)
    song: reactive[dict] = reactive({})

    def __init__(self, album, **kwargs) -> None:
        super().__init__(**kwargs)
        self.album = album

    @property
    def is_playing(self) -> bool:
        return self.song.get("albumId", -1) == self.album.get("id", "")

    def watch_song(self, old, new) -> None:
        if self.is_playing:
            self.classes = "current"
            songs: list = self.album.get("song", [])
            album_songs: int = len(songs)
            current_song: int = songs.index(self.song)
            self.border_subtitle = f"{current_song + 1}/{album_songs}"
            if current_song == 0:
                self.scroll_visible(animate=True)
        else:
            self.border_subtitle = ""
            self.classes = ""

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal(classes="album-title"):
                yield Label("    ", classes="icon")
                yield Label(self.album["artist"], classes="artist")
                yield Label(" - ", classes="label")
                yield Label(self.album["name"], classes="album")
                year = self.album.get("year", 0)
                if year:
                    year = f"[{year}]"
                yield Label(year, classes="year")
                yield Label(
                    f"󰔚 {format_time(self.album['duration'])}", classes="duration"
                )
            for song in self.album["song"]:
                yield PlaylistSongWidget(song=song).data_bind(
                    current_playing=PlaylistAlbumWidget.song
                )
        art = AlbumArt(self.album.get("coverArt", ""))
        yield art


class PlaylistSongWidget(Widget, can_focus=True):
    current_playing: reactive[dict] = reactive(dict)

    class Play(Message):
        def __init__(self, song: dict) -> None:
            super().__init__()
            self.song = song

    BINDINGS = [  # noqa: RUF012
        Binding("enter", "play", "Play song", priority=True)
    ]

    def __init__(self, song: dict, **kwargs) -> None:
        super().__init__(**kwargs)
        self.song = song

    def watch_current_playing(self, old: dict, new: dict) -> None:
        if self.song == new or self.song == old:
            self.refresh(recompose=True)
            self.classes = "current" if self.song == new else ""
            if self.song.get("track", 1) != 1:
                self.scroll_visible()

    def compose(self) -> ComposeResult:

        track = self.song.get("track", "")
        if track:
            track = f"{track:2}. "
        artist = self.song.get("artist", "No artist")
        title = self.song.get("title", "No title")
        duration = format_time(self.song.get("duration", 0), padminutes=False)
        if self.song == self.current_playing:
            yield Playing(classes="icon")
        else:
            track = "  " + track
        yield Label(track, classes="track")
        yield Label(artist, classes="artist")
        yield Label(" - ", classes="label")
        yield Label(title, classes="title")
        yield Label(duration, classes="duration")

    def on_click(self, event: Click) -> None:
        if event.chain == 2:
            self.action_play()

    def action_play(self) -> None:
        self.post_message(self.Play(self.song))
        # self.current_playing = self.song


class Playing(Static):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._spinner = Spinner("arc", style="")
        self.update(self._spinner)

    def on_mount(self) -> None:
        self.set_interval(1 / 60, self.update_spinner)

    def update_spinner(self) -> None:
        self.update(self._spinner)
