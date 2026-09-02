from http.client import HTTPResponse
from pathlib import Path

from platformdirs import user_cache_dir
from textual import work
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual_image.widget import Image


class AlbumArt(Widget):
    aid: reactive[str] = reactive("")

    def __init__(self, aid: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.image = Image("", classes="album")
        self.aid = aid

    def compose(self) -> ComposeResult:
        yield self.image

    def on_mount(self) -> None:
        if self.aid:
            self.download_image()

    def update_image(self, path) -> None:
        self.image.image = path

    # def watch_aid(self, old, new) -> None:
    #     if new:
    #         print(f"aid: {new}")
    #         # self.download_image()

    @work(thread=True)
    def download_image(self) -> None:
        cache_dir = Path(user_cache_dir("capy"))
        cache_dir.mkdir(parents=True, exist_ok=True)
        image = cache_dir / self.aid
        if not image.exists():
            response: HTTPResponse = self.app.conn.getCoverArt(self.aid)  # pyright: ignore
            with open(image, mode="wb") as file:
                file.write(response.read())
        self.app.call_from_thread(self.update_image, image.absolute())
