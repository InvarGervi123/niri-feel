"""Compact top-center brightness OSD using the project's layer-shell stack."""
import time
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')
from gi.repository import Gtk, GLib, Gtk4LayerShell as Layer
from .brightness_estimate import estimate, discharge_watts
from .floating_ui import draw_glyph


class BrightnessOSD(Gtk.ApplicationWindow):
    def __init__(self, app, monitor):
        super().__init__(application=app)
        self.set_title('Niri Feel Brightness')
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_focusable(False)
        Layer.init_for_window(self)
        Layer.set_namespace(self, 'niri-feel-brightness')
        Layer.set_monitor(self, monitor)
        Layer.set_layer(self, Layer.Layer.OVERLAY)
        Layer.set_anchor(self, Layer.Edge.TOP, True)
        Layer.set_margin(self, Layer.Edge.TOP, 54)
        Layer.set_exclusive_zone(self, -1)
        Layer.set_keyboard_mode(self, Layer.KeyboardMode.NONE)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.add_css_class('feel-surface')
        box.add_css_class('feel-brightness')
        row = Gtk.Box(spacing=7)
        icon = Gtk.DrawingArea()
        icon.set_content_width(20); icon.set_content_height(20)
        icon.set_draw_func(lambda _area, cr, _w, _h: draw_glyph(cr, 'brightness', 20))
        self.percent = Gtk.Label(xalign=0); self.percent.add_css_class('feel-value')
        row.append(icon); row.append(self.percent); box.append(row)
        self.bar = Gtk.ProgressBar(); self.bar.set_show_text(False); box.append(self.bar)
        self.secondary = Gtk.Label(xalign=0); self.secondary.add_css_class('feel-muted'); box.append(self.secondary)
        self.set_child(box)
        self.set_default_size(258, -1)
        self.set_opacity(0)
        self.timer = self.fade = 0
        self.generation = 0
        self.online = self.battery = None

    def update_power(self, online, battery):
        self.online, self.battery = online, battery
        self._refresh_secondary()

    def _refresh_secondary(self):
        values = [value for value in (discharge_watts(self.battery, self.online),
                                      estimate(self.battery, self.online)) if value]
        self.secondary.set_text('  ·  '.join(values))
        self.secondary.set_visible(bool(values))

    def show_level(self, value, displays):
        if value is None:
            return
        self.percent.set_text(f'{value}%')
        self.bar.set_fraction(value / 100)
        self._refresh_secondary()
        self.present()
        self.set_opacity(1)
        self.generation += 1
        generation = self.generation
        self.timer = GLib.timeout_add(1700, self._fade, generation)

    def _fade(self, generation):
        if generation != self.generation:
            return GLib.SOURCE_REMOVE
        self.timer = 0
        start = time.monotonic()
        def tick():
            if generation != self.generation:
                self.fade = 0
                return GLib.SOURCE_REMOVE
            opacity = max(0, 1 - (time.monotonic() - start) / .28)
            self.set_opacity(opacity)
            if opacity <= 0:
                self.fade = 0
                return GLib.SOURCE_REMOVE
            return GLib.SOURCE_CONTINUE
        self.fade = GLib.timeout_add(16, tick)
        return GLib.SOURCE_REMOVE

    def stop(self):
        self.generation += 1
        self.destroy()
