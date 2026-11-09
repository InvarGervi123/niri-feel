"""A small bottom-edge light field. No persistent frame callbacks."""
import time
import cairo
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gtk, Gdk, GLib, Gtk4LayerShell as Layer

from .render import render
from .session_visual import render_summary, SUMMARY_DURATION, SUMMARY_HEIGHT

DURATION = 3.4

class EdgeLight(Gtk.ApplicationWindow):
    def __init__(self, app, monitor):
        super().__init__(application=app)
        self.kind = "connect"
        self.title_text = self.detail = ""
        self.started = 0
        self.tick_id = 0
        self.frames = 0
        self.summary = None
        self.duration = DURATION
        self.set_title("Niri Feel")
        self.set_decorated(False)
        self.set_focusable(False)
        self.set_can_focus(False)
        Layer.init_for_window(self)
        Layer.set_namespace(self, "niri-feel")
        Layer.set_monitor(self, monitor)
        Layer.set_layer(self, Layer.Layer.OVERLAY)
        for edge in (Layer.Edge.BOTTOM, Layer.Edge.LEFT, Layer.Edge.RIGHT):
            Layer.set_anchor(self, edge, True)
        Layer.set_exclusive_zone(self, -1)
        Layer.set_keyboard_mode(self, Layer.KeyboardMode.NONE)
        self.area = Gtk.DrawingArea()
        self.area.set_content_height(108)
        self.area.set_draw_func(self.draw)
        self.area.set_can_target(False)
        self.set_child(self.area)
        self.connect("realize", self.realized)

    def realized(self, *_):
        # Empty Wayland input region: every click reaches the application below.
        self.get_surface().set_input_region(cairo.Region())

    def play(self, kind, title, detail, summary=None):
        self.summary = summary
        self.duration = SUMMARY_DURATION if summary is not None else DURATION
        height = SUMMARY_HEIGHT if summary is not None else 108
        self.area.set_content_height(height)
        self.set_default_size(-1, height)
        self.kind, self.title_text, self.detail = kind, title, detail
        self.started = time.monotonic()
        self.frames = 0
        self.set_visible(True)
        if not self.tick_id:
            self.tick_id = self.area.add_tick_callback(self.tick)
        self.area.queue_draw()

    def tick(self, widget, clock):
        self.frames += 1
        if time.monotonic() - self.started >= self.duration:
            self.tick_id = 0
            self.set_visible(False)
            return GLib.SOURCE_REMOVE
        self.area.queue_draw()
        return GLib.SOURCE_CONTINUE

    def stop(self):
        if self.tick_id:
            self.area.remove_tick_callback(self.tick_id)
            self.tick_id = 0
        self.destroy()

    def draw(self, area, cr, width, height):
        elapsed = time.monotonic() - self.started
        render(cr, width, height, elapsed, self.kind,
               "" if self.summary is not None else self.title_text,
               "" if self.summary is not None else self.detail)
        if self.summary is not None:
            render_summary(cr, width, height, elapsed, self.summary)

