from libsonic import Connection
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.events import Click
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, Label

from capy.albumart import AlbumArt
from capy.utils import format_time


class Search(Widget):
    def __init__(self, conn: Connection, **kwargs) -> None:
        super().__init__(**kwargs)
        self.conn = conn
        self.last = None

    class Cancel(Message):
        pass

    def compose(self) -> ComposeResult:
        yield Input(id="query", placeholder="Search terms")
        self.results = SearchResults()
        yield self.results

    @work(thread=True)
    @on(Input.Submitted)
    def search(self, event: Input.Submitted) -> None:
        def on():
            self.results.loading = True

        def back():
            self.results.loading = False

        self.app.call_from_thread(on)
        if event.value:
            if event.value != self.last:
                self.results.results = self.conn.search3(event.value, songCount=100)[
                    "searchResult3"
                ]
            else:
                if self.results.results:
                    # self.app.call_from_thread(self.app.action_focus_next)
                    self.call_later(self.app.action_focus_next)

        else:
            self.results.results = {}
        self.last = event.value

        self.app.call_from_thread(back)


class SearchResults(Widget):
    results: reactive[dict] = reactive({}, recompose=True)

    def compose(self) -> ComposeResult:
        artists = self.results.get("artist", [])
        albums = self.results.get("album", [])
        songs = self.results.get("song", [])
        if artists:
            yield Label(f"  Artists ({len(artists)})", classes="group")
            for artist in artists:
                yield SearchResultArtist(artist)
        if albums:
            yield Label(f"  Albums ({len(albums)})", classes="group")
            for album in albums:
                yield SearchResultAlbum(album)
        if songs:
            songs = sorted(songs, key=lambda x: (x["artist"], x["album"], x["track"]))
            yield Label(f"󰎄  Songs ({len(songs)})", classes="group")
            for song in songs:
                yield SearchResultSong(song)
        if not songs and not albums and not artists:
            self.log("empty")
            yield Container(Label("\\[No results]"), classes="empty")


class SearchResultArtist(Widget, can_focus=True):
    BINDINGS = [  # noqa: RUF012
        ("enter", "play", "Play")
    ]

    class Play(Message):
        def __init__(self, artist: dict) -> None:
            super().__init__()
            self.artist = artist

    def __init__(self, artist, **kwargs):
        super().__init__(**kwargs)
        self.artist = artist

    def compose(self) -> ComposeResult:
        yield AlbumArt(aid=self.artist["coverArt"])
        with Vertical():
            yield Label(self.artist["name"], classes="highlight")
            yield Label(f"{self.artist.get('albumCount', 0)} albums")

    def action_play(self) -> None:
        self.post_message(self.Play(self.artist))


class SearchResultAlbum(Widget, can_focus=True):
    BINDINGS = [  # noqa: RUF012
        ("enter", "play", "Play")
    ]

    class Play(Message):
        def __init__(self, album: dict) -> None:
            super().__init__()
            self.album = album

    def __init__(self, album, **kwargs):
        super().__init__(**kwargs)
        self.album = album

    def compose(self) -> ComposeResult:
        yield AlbumArt(aid=self.album["coverArt"])
        with Vertical():
            yield Label(self.album["name"], classes="highlight")
            yield Label(f"{self.album['artist']}, {self.album['songCount']} songs")

    def on_click(self, event: Click) -> None:
        if event.chain == 2:
            self.action_play()

    def action_play(self) -> None:
        self.post_message(self.Play(self.album))


class SearchResultSong(Widget, can_focus=True):
    BINDINGS = [  # noqa: RUF012
        ("enter", "play", "Play")
    ]

    class Play(Message):
        def __init__(self, song: dict) -> None:
            super().__init__()
            self.song = song

    def on_click(self, event: Click) -> None:
        if event.chain == 2:
            self.action_play()

    def action_play(self) -> None:
        self.post_message(self.Play(self.song))

    def __init__(self, song, **kwargs):
        super().__init__(**kwargs)
        self.song = song

    def compose(self) -> ComposeResult:
        yield Label(
            f"{self.song['artist']} - {self.song['album']} - {self.song['track']}. "
        )
        yield Label(self.song["title"], classes="highlight")
        yield Label(format_time(self.song["duration"], padminutes=False))
