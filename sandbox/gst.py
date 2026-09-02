import os
import sys

import gi

# 1. Require GStreamer 1.0 before importing
gi.require_version("Gst", "1.0")
from gi.repository import GLib, Gst


def on_message(bus: Gst.Bus, message: Gst.Message, loop: GLib.MainLoop):
    """Callback function to handle pipeline messages from the bus."""
    t = message.type
    if t == Gst.MessageType.EOS:
        print("\nEnd of stream reached.")
        loop.quit()
    elif t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        print(f"\nError: {err.message}")
        if debug:
            print(f"Debug info: {debug}")
        loop.quit()
    else:
        print(t)
    return True


def main():
    # Check for input file argument
    if len(sys.argv) < 2:
        print(f"Usage: python {os.path.basename(__file__)} <path/to/media/file>")
        return

    filepath = os.path.abspath(sys.argv[1])
    if not os.path.exists(filepath):
        print(f"Error: File not found at '{filepath}'")
        return

    # 2. Initialize GStreamer
    Gst.init(None)

    # 3. Create the 'playbin' element acting as our pipeline
    pipeline = Gst.ElementFactory.make("playbin", "player")
    if not pipeline:
        print(
            "Error: Could not create 'playbin' element. Is GStreamer fully installed?"
        )
        return

    # Convert local file path to a valid URI
    file_uri = GLib.filename_to_uri(filepath, None)
    pipeline.set_property("uri", file_uri)

    # 4. Connect to the pipeline's message bus
    bus = pipeline.get_bus()
    bus.add_signal_watch()

    # 5. Create a GLib main loop to handle events asynchronously
    loop = GLib.MainLoop()
    bus.connect("message", on_message, loop)

    # 6. Start playback
    print(f"Playing: {filepath}")
    print("Press Ctrl+C to stop.")
    pipeline.set_state(Gst.State.PLAYING)

    try:
        loop.run()
    except KeyboardInterrupt:
        print("\nPlayback interrupted by user.")
    finally:
        # 7. Clean up and set pipeline back to NULL state
        pipeline.set_state(Gst.State.NULL)


if __name__ == "__main__":
    main()
