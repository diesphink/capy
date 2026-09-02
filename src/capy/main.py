#!/bin/env python

import os
import random
import time

import libsonic
import pylast
from textual import on, work
from textual.app import App, ComposeResult
from textual.events import DescendantFocus
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, Label, TabbedContent, TabPane

from capy.audio.audio_backend import EventType
from capy.audio.gst_backend import GstBackend
from capy.current_playing import CurrentPlaying
from capy.model import PlayingStatus
from capy.mpris import MPRISBackend
from capy.playlist import AlbumPlaylist, PlaylistSongWidget, PlaylistWidget
from capy.search import Search, SearchResultAlbum, SearchResultArtist, SearchResultSong


# https://github.com/Textualize/textual/issues/4955#issuecomment-3192581804
class WrappedTabPane(TabPane):
    def _on_descendant_focus(self, event: DescendantFocus):
        event.stop()
        event.prevent_default()


class Lyrics(Widget):
    song: reactive[dict] = reactive({})

    def compose(self) -> ComposeResult:

        if "lyrics" in self.song:
            yield Label(self.song["lyrics"])


class Capy(App):
    BINDINGS = [  # noqa: RUF012
        ("ctrl+n", "play_random", "Play random song"),
        ("d", "debug", "Debug"),
        ("n", "next_song", "Next song"),
        ("q", "quit", "Quit"),
        ("space", "player_toggle", "Toggle"),
        ("down,j", "focus_next", "Next"),
        ("up,k", "focus_previous", "Previous"),
        ("/", "search", "Search"),
        ("escape", "cancel", "Cancel"),
    ]
    CSS_PATH = "capy.tcss"

    playlist: reactive[AlbumPlaylist] = reactive(AlbumPlaylist())
    status: reactive[PlayingStatus] = reactive(PlayingStatus())
    song: reactive[dict] = reactive({})

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.conn: libsonic.Connection = libsonic.Connection(
            baseUrl=os.environ.get("SUBSONIC_HOST"),
            username=os.environ.get("SUBSONIC_USER"),
            password=os.environ.get("SUBSONIC_PASSWORD"),
            port=int(os.environ.get("SUBSONIC_PORT", "4533")),
        )
        self.lastfm = pylast.LastFMNetwork(
            api_key=os.environ.get("LASTFM_APIKEY", ""),
            api_secret=os.environ.get("LASTFM_APISECRET", ""),
            username=os.environ.get("LASTFM_USER", ""),
            password_hash=os.environ.get("LASTFM_PASSHASH", ""),
        )
        self.mpris = MPRISBackend(PlayingStatus(), {}, self)
        self.audio = GstBackend(self.conn)
        self.audio.init()
        self.audio.on_event(EventType.MUSIC_END, self.action_next_song)
        self.audio.on_event(EventType.STATUS_PAUSED, self.on_status_paused)
        self.audio.on_event(EventType.STATUS_PLAYING, self.on_status_playing)

    @property
    def album(self) -> dict:
        return next(
            (x for x in self.playlist.albums if x["id"] == self.song["albumId"]), {}
        )

    def on_mount(self) -> None:
        # Define o tema
        self.theme = "catppuccin-macchiato"

        # Inicia os loops
        self.audio_loop()
        self.set_interval(1.25, self.update_track_position)
        self.mpris_loop()

        # Começa a tocar música
        self.action_play_random()

    def on_unmount(self) -> None:
        self.audio.destroy()
        self.mpris.destroy()

    def compose(self) -> ComposeResult:
        yield (CurrentPlaying().data_bind(Capy.song).data_bind(Capy.status))
        with TabbedContent():
            with WrappedTabPane("Playlist", id="playlist"):
                yield PlaylistWidget().data_bind(Capy.song).data_bind(Capy.playlist)

            with WrappedTabPane("Search", id="search"):
                yield Search(self.conn)

            with WrappedTabPane("Lyrics", id="lyrics"):
                yield Lyrics().data_bind(Capy.song)

    @on(PlaylistSongWidget.Play)
    def on_song_play_playlist(self, message) -> None:
        self.song = message.song

    @work(thread=True)
    @on(SearchResultSong.Play)
    def on_song_play_search(self, message) -> None:

        self.log(message.song)
        album: dict = self.conn.getAlbum(message.song["albumId"])["album"]
        self.playlist.albums = [album]
        self.mutate_reactive(Capy.playlist)
        self.song = next(x for x in album["song"] if x["id"] == message.song["id"])
        self.call_from_thread(self.action_cancel)

    @work(thread=True)
    @on(SearchResultAlbum.Play)
    def on_album_play(self, message: SearchResultAlbum.Play) -> None:
        album: dict = self.conn.getAlbum(message.album["id"])["album"]
        self.playlist.albums = [album]
        self.mutate_reactive(Capy.playlist)
        self.song = album["song"][0]
        self.call_from_thread(self.action_cancel)

    @work(thread=True)
    @on(SearchResultArtist.Play)
    def on_artist_play(self, message: SearchResultArtist.Play) -> None:
        artist = self.conn.getArtist(message.artist["id"])["artist"]
        albums = []
        for album in artist["album"]:
            albums.append(self.conn.getAlbum(album["id"])["album"])
        random.shuffle(albums)
        self.playlist.albums = albums
        self.mutate_reactive(Capy.playlist)
        self.song = self.playlist.albums[0]["song"][0]
        self.call_from_thread(self.action_cancel)

    @work(thread=True)
    def audio_loop(self) -> None:
        self.audio.loop()

    @work(thread=True)
    async def mpris_loop(self) -> None:
        await self.mpris.loop()

    def update_track_position(self) -> None:
        position = self.audio.get_position()
        if position != self.status.position:
            self.status.position = position
            self.mutate_reactive(Capy.status)

    def on_status_paused(self) -> None:
        self.status.state = "paused"
        self.mutate_reactive(Capy.status)

    def on_status_playing(self) -> None:
        self.status.state = "playing"
        self.mutate_reactive(Capy.status)

    def watch_song(self, old: dict, new: dict) -> None:
        self.audio.play(new)
        self.status.duration = new.get("duration", 0)
        self.status.position = 0
        self.mutate_reactive(Capy.status)
        self.mpris.song = self.song
        self.scrobble()

    def watch_status(self, old: PlayingStatus, new: PlayingStatus) -> None:
        if self.mpris:
            self.mpris.status = new

    @work(thread=True)
    def scrobble(self) -> None:
        if "title" in self.song:
            payload = {
                "artist": self.song.get("artist", ""),
                "title": self.song.get("title", ""),
                "album": self.song.get("album", ""),
                "mbid": self.song.get("mbid", ""),
                "duration": self.song.get("duration", ""),
                "track_number": self.song.get("duration", ""),
            }
            # self.lastfm.update_now_playing(**payload)
            self.lastfm.scrobble(timestamp=int(time.time()), **payload)

    def action_next_song(self) -> None:
        songs: list = self.album["song"]
        next_index = songs.index(self.song) + 1
        if next_index >= len(songs):
            next_album_index = self.playlist.albums.index(self.album) + 1
            if next_album_index >= len(self.playlist.albums):
                self.action_play_random()
            else:
                self.song = self.playlist.albums[next_album_index]["song"][0]
        else:
            self.song = songs[next_index]

    @on(TabbedContent.TabActivated)
    def on_tab(self, event: TabbedContent.TabActivated) -> None:
        if event.pane.id == "search":
            self.query_one(Input).focus()

    def action_cancel(self) -> None:
        tabs = self.query_one(TabbedContent)
        if tabs.active == "search":
            self.query_one(TabbedContent).active = "playlist"

    @work(thread=True)
    def action_play_random(self) -> None:
        self.playlist.albums.clear()

        albums = self.conn.getAlbumList2(ltype="random", size=4)
        for album in albums["albumList2"]["album"]:
            album = self.conn.getAlbum(album["id"])["album"]
            self.playlist.albums.append(album)

        self.song = self.playlist.albums[0]["song"][0]
        self.mutate_reactive(Capy.playlist)
        self.audio.play(self.song)

    def action_debug(self) -> None:
        self.log(self.album)
        self.log(self.conn.search3(query="doll"))

    def action_player_toggle(self) -> None:
        self.audio.toggle()

    def action_search(self) -> None:
        tabs = self.query_one(TabbedContent)
        if tabs.active != "search":
            tabs.active = "search"
        else:
            self.call_after_refresh(lambda: self.query_one(Input).focus())


if __name__ == "__main__":
    app = Capy()
    app.run()
