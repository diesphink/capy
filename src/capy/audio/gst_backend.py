import threading
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from http.client import HTTPResponse
from zoneinfo import ZoneInfo

import gi
from libsonic import Connection

from capy.audio.audio_backend import EventType

gi.require_version("Gst", "1.0")
from gi.repository import GLib, Gst

tags = {}


class GstBackend:
    def __init__(self, conn: Connection) -> None:
        self.pipeline: gi.Repository.Gst.Pipeline = None
        self.bus = None
        self.current_response: HTTPResponse | None = None
        self.current_song: dict
        self.is_pushing = False
        self.conn = conn
        self.hooks_end = []
        self.hooks: dict[EventType, list[Callable]] = defaultdict(list)
        self.lock = threading.Lock()

    def init(self) -> None:
        GLib.set_application_name("Capy")
        Gst.init(None)

        self.mloop = GLib.MainLoop.new()
        self.create_pipeline()

    def flush_pipeline(self) -> None:
        if self.pipeline:
            self.pipeline.send_event(Gst.Event.new_flush_start())
            self.pipeline.send_event(Gst.Event.new_flush_stop(True))

    def get_position(self) -> int:
        _, position = self.pipeline.query_position(Gst.Format.TIME)
        return int(position / Gst.SECOND)

    def create_pipeline(self) -> None:
        # self.log("Recreating pipeline")
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline.get_state(Gst.CLOCK_TIME_NONE)

        if self.bus and self.handler:
            self.bus.disconnect(self.handler)
            self.bus.remove_signal_watch()

        self.pipeline = Gst.parse_launch(
            "appsrc name=mysource emit-signals=true ! decodebin ! audioconvert ! audioresample ! taginject name=mytags ! autoaudiosink"
        )
        self.appsrc = self.pipeline.get_by_name("mysource")
        self.taginject = self.pipeline.get_by_name("mytags")

        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()

        self.handler = self.bus.connect("message", self.on_message, self.mloop)
        self.appsrc.connect("need-data", self._on_need_data)
        self.appsrc.connect("enough-data", self._on_enough_data)

    def on_message(self, bus: Gst.Bus, message: Gst.Message, loop: GLib.MainLoop):
        if message.type == Gst.MessageType.TAG:
            tag_list = message.parse_tag()

            if not tag_list:
                return

            def callback_print_tag(list_of_tags, tag_name, user_data):
                new_value = list_of_tags.get_string(tag_name)[1]
                if tag_name in tags and tags[tag_name] != new_value:
                    # print(f"TAGS: {tag_name}: {tags[tag_name]} -> {new_value}")
                    pass
                if tag_name not in tags:
                    # print(f"TAGS: {tag_name}: {new_value}")
                    pass
                tags[tag_name] = new_value

            tag_list.foreach(callback_print_tag, None)
        elif message.type == Gst.MessageType.WARNING:
            err, debug = message.parse_warning()
            self.log(f"Warning from {message.src.get_name()}: {err}")
            if debug:
                print(f"Debug info: {debug}")
        elif message.type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"Error from {message.src.get_name()}: {err}")
            if debug:
                print(f"Debug info: {debug}")
        elif message.type == Gst.MessageType.EOS:
            for function in self.hooks[EventType.MUSIC_END]:
                function()
        # elif message.type == Gst.MessageType.PLAYING:
        #     for function in self.hooks[EventType.MUSIC_END]:
        #         function()
        elif message.type == Gst.MessageType.STATE_CHANGED:
            element_name = message.src.get_name()
            if element_name == "mysource":
                _, new_state, _ = message.parse_state_changed()

                # self.log(f"mysource: {new_state.value_nick}")
                # print(
                #     f"Element '{element_name}' changed state "
                #     f"from {old_state.value_nick} to {new_state.value_nick} "
                #     f"(pending: {pending_state.value_nick})"
                # )
                if new_state.value_nick == "paused":
                    for function in self.hooks[EventType.STATUS_PAUSED]:
                        function()
                if new_state.value_nick == "playing":
                    for function in self.hooks[EventType.STATUS_PLAYING]:
                        function()
        elif (
            message.type == Gst.MessageType.NEW_CLOCK
            or message.type == Gst.MessageType.STREAM_START
            or message.type == Gst.MessageType.STREAM_STATUS
            or message.type == Gst.MessageType.LATENCY
            or message.type == Gst.MessageType.ASYNC_DONE
            or message.type == Gst.MessageType.DURATION_CHANGED
            or message.type == Gst.MessageType.RESET_TIME
        ):
            self.log(f"type: {message.type}")
        else:
            print(f"Any: {message.type}, {dir(message)}")

        return True

    def on_event(self, event_type: EventType, fn: Callable) -> None:
        self.hooks[event_type].append(fn)

    def play(self, song: dict | None = None):
        if song:
            with self.lock:
                if self.current_response:
                    try:
                        self.flush_pipeline()
                        self.current_response.close()
                        if self.current_song["contentType"] != song["contentType"]:
                            self.create_pipeline()
                    except Exception as e:  # noqa (Não é ok capturar todos os erros assim)
                        self.log(e)
                self.current_response = self.conn.stream(song["id"], tformat="mp3")  # pyright: ignore (Erro de tipo, ele de fato retorna um HTTPReseponse)

                self.current_song = song
                self.pipeline.set_state(Gst.State.PLAYING)
            self.taginject.set_property(
                "tags",
                f'title="{song["title"]}",artist="{song["artist"]}",album="{song["album"]}"',
            )
        else:
            self.pipeline.set_state(Gst.State.PLAYING)

    def log(self, text):
        now = datetime.now(tz=ZoneInfo("America/Sao_Paulo")).strftime("%H:%M:%S")
        print(f"[{now}] {text}")

    def _on_need_data(self, appsrc, length):
        if not self.is_pushing:
            self.is_pushing = True
            # self.log("New thread!")
            threading.Thread(target=self._push_data, daemon=True).start()

    def _on_enough_data(self, appsrc):
        # self.log("enough data")
        self.is_pushing = False

    def loop(self):
        self.mloop.run()

    def _push_data(self):
        chunk_size = 4096
        # self.log("pushing")

        while self.is_pushing:
            with self.lock:
                response = self.current_response

            if not response:
                self.log("No response")
                break

            try:
                chunk = response.read(chunk_size)
            except Exception as e:  # noqa (Não é ok capturar todos os erros assim)
                self.log("Exception ao ler")
                self.log(e)
                break

            if not chunk:
                self.appsrc.emit("end-of-stream")
                # self.log("End of stream")
                break
            else:
                ret = self.appsrc.emit("push-buffer", Gst.Buffer.new_wrapped(chunk))
                if ret != Gst.FlowReturn.OK:
                    self.log(f" {ret} Erro ao empurrar buffer")

        # self.log("Done")
        self.is_pushing = False

    def pause(self) -> None:
        self.pipeline.set_state(Gst.State.PAUSED)

    def toggle(self) -> None:
        _, current, _ = self.pipeline.get_state(Gst.CLOCK_TIME_NONE)

        if current == Gst.State.PLAYING:
            self.pause()
        elif current == Gst.State.PAUSED:
            self.play()

    def destroy(self) -> None:
        self.pipeline.set_state(Gst.State.NULL)
        self.mloop.quit()
