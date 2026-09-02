from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Tabs


class CapyTabs(Widget):
    def compose(self) -> ComposeResult:
        yield Tabs("Playlist", "Search")
