import asyncio
from pathlib import Path

from dbus_next.aio.message_bus import MessageBus
from dbus_next.constants import PropertyAccess
from dbus_next.service import ServiceInterface, dbus_property, method
from dbus_next.signature import Variant
from platformdirs import user_cache_dir

from capy.model import PlayingStatus


class MPRISRootService(ServiceInterface):
    def __init__(self) -> None:
        super().__init__("org.mpris.MediaPlayer2")

    def CanQuit(self) -> "b":
        return False

    @dbus_property(access=PropertyAccess.READ)
    def CanRaise(self) -> "b":
        return False

    @dbus_property(access=PropertyAccess.READ)
    def HasTrackList(self) -> "b":
        return False

    @dbus_property(access=PropertyAccess.READ)
    def Identity(self) -> "s":
        return "Capy"

    @dbus_property(access=PropertyAccess.READ)
    def DesktopEntry(self) -> "s":
        return ""

    @dbus_property(access=PropertyAccess.READ)
    def SupportedUriSchemes(self) -> "as":
        return []

    @dbus_property(access=PropertyAccess.READ)
    def SupportedMimeTypes(self) -> "as":
        return []


class MPRISBackend(ServiceInterface):
    def __init__(self, status: PlayingStatus, song: dict, app) -> None:
        super().__init__("org.mpris.MediaPlayer2.Player")
        self.future: asyncio.Future | None = None
        self.status: PlayingStatus = status
        self.song: dict = song
        self.app = app

    async def loop(self):
        bus = await MessageBus().connect()
        bus.export("/org/mpris/MediaPlayer2", MPRISRootService())
        bus.export("/org/mpris/MediaPlayer2", self)

        # Request an MPRIS-compliant Bus Name (must start with org.mpris.MediaPlayer2)
        await bus.request_name("org.mpris.MediaPlayer2.Capy")

        # Keep the event loop running
        self.runloop = asyncio.get_running_loop()
        self.future = self.runloop.create_future()

        try:
            await self.future
        except asyncio.CancelledError:
            print("Cancelled")

    def destroy(self) -> None:
        print("Cancelling...")
        # asyncio.get_event_loop().stop()

        # Verifica se o loop e o future existem e se o loop ainda está rodando
        if self.runloop and self.future and self.runloop.is_running():
            # call_soon_threadsafe garante que funciona mesmo se destroy
            # for chamado de fora do loop do asyncio (ex: outra thread)
            self.runloop.call_soon_threadsafe(self.future.set_result, None)

    @method()
    def Play(self):
        self.app.action_player_toggle()

    @method()
    def Pause(self):
        self.app.action_player_toggle()

    @method()
    def PlayPause(self):
        self.app.action_player_toggle()

    @method()
    def Stop(self):
        self.app.action_player_toggle()

    @dbus_property(access=PropertyAccess.READ)
    def PlaybackStatus(self) -> "s":
        return self.status.state.capitalize()

    @dbus_property(access=PropertyAccess.READ)
    def Metadata(self) -> "a{sv}":
        # Minimum metadata mapping to make control widgets display something
        if "coverArt" in self.song:
            cache_dir = Path(user_cache_dir("capy"))
            cache_dir.mkdir(parents=True, exist_ok=True)
            image = cache_dir / self.song.get("coverArt", "")
        else:
            image = ""
        return {
            "mpris:trackid": Variant(
                "o", f"/org/mpris/MediaPlayer2/Track/{self.song['id']}"
            ),
            "xesam:title": Variant("s", self.song.get("title", "")),
            "xesam:artist": Variant("as", [self.song.get("artist", "")]),
            "xesam:album": Variant("s", self.song.get("album", "")),
            "mpris:length": Variant("x", self.song.get("duration", 0) * (10**6)),
            "mpris:artUrl": Variant("s", str(image)),
        }

    # Rest of the mandatory MPRIS properties with minimal values
    @dbus_property(access=PropertyAccess.READ)
    def Rate(self) -> "d":
        return 1.0

    @dbus_property(access=PropertyAccess.READ)
    def Volume(self) -> "d":
        return 1.0

    @dbus_property(access=PropertyAccess.READ)
    def Position(self) -> "x":
        return self.status.position * (10**6)

    @dbus_property(access=PropertyAccess.READ)
    def MinimumRate(self) -> "d":
        return 1.0

    @dbus_property(access=PropertyAccess.READ)
    def MaximumRate(self) -> "d":
        return 1.0

    @dbus_property(access=PropertyAccess.READ)
    def CanGoNext(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanGoPrevious(self) -> "b":
        return False

    @dbus_property(access=PropertyAccess.READ)
    def CanPlay(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanPause(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanSeek(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanControl(self) -> "b":
        return True
