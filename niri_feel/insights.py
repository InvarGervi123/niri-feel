"""A small on-demand energy story; no component percentages or inferred remainder."""
import time
import cairo
from gi.repository import Gtk, Gdk, GLib
from .energy import Ledger


def duration(seconds):
    return f"{seconds/60:.1f} min" if seconds >= 60 else f"{seconds:.0f} s"


def wh(value):
    return f"{value:.4f} Wh"


def preview_ledger():
    ledger = Ledger()
    ledger.awake_wh, ledger.awake_pp, ledger.awake_seconds = .84, 2, 420
    ledger.cpu_wh, ledger.cpu_seconds, ledger.live_cpu_w = .31, 420, 2.7
    ledger.sleep_wh, ledger.sleep_pp, ledger.sleep_seconds = .12, 1, 1800
    ledger.awake_intervals = ledger.sleep_intervals = ledger.pp_intervals = ledger.sleep_pp_intervals = 1
    ledger.last_interval = "Preview · simulated readings"
    return ledger

class Insights(Gtk.ApplicationWindow):
    def __init__(self, app, service, preview=False):
        super().__init__(application=app, title="Niri Feel · Energy")
        self.service, self.preview = service, preview
        self.demo = preview_ledger() if preview else None
        self.set_default_size(460, 620)
        self.set_resizable(False)
        self.add_css_class("energy-window")
        css = Gtk.CssProvider()
        css.load_from_data(b"""
        window.energy-window { background: #101c21; color: #e5f4f0; }
        .energy-body { padding: 24px; }
        .eyebrow { color: #8ad9be; font-size: 11px; letter-spacing: 2px; }
        .energy-title { font-size: 25px; font-weight: 500; }
        .energy-value { font-size: 31px; font-weight: 400; color: #d6f7ea; }
        .energy-small { font-size: 12px; color: #a5bcb8; }
        .energy-note { font-size: 11px; color: #8da5a4; }
        .energy-row { padding: 10px 0; }
        button { background: #1d3437; color: #e5f4f0; border-radius: 12px; padding: 7px 16px; }
        """)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION+1)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.add_css_class("energy-body")
        self.set_child(box)
        self.labels = {}
        def label(key, style, text=""):
            widget = Gtk.Label(label=text, xalign=0)
            widget.set_wrap(True)
            widget.add_css_class(style)
            box.append(widget)
            self.labels[key] = widget
        label("tag", "eyebrow", "ENERGY / PREVIEW · SIMULATED" if preview else "ENERGY / SINCE LAUNCH")
        label("title", "energy-title", "Where did my energy go?")
        self.field = Gtk.DrawingArea()
        self.field.set_content_height(98)
        self.field.set_draw_func(self.draw_field)
        box.append(self.field)
        label("total", "energy-value")
        label("battery", "energy-small")
        label("cpu", "energy-small")
        label("sleep", "energy-small")
        label("unknown", "energy-note", "Screen · SSD · RAM\nNot measured independently on this system.")
        label("meaning", "energy-note", "These are separate readings, not a breakdown. CPU package includes overlapping internal domains. No remainder is assigned to other components.")
        label("status", "energy-note")
        label("coverage", "energy-note")
        footer = Gtk.Box(spacing=8)
        close = Gtk.Button(label="Close")
        close.connect("clicked", lambda _: self.close())
        footer.append(close)
        box.append(footer)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self.key_pressed)
        self.add_controller(keys)
        self.connect("close-request", self.on_close)
        self.started = time.monotonic()
        self.entry_tick = self.field.add_tick_callback(self.animate_entry)
        self.refresh()

    def key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def animate_entry(self, widget, clock):
        self.field.queue_draw()
        if time.monotonic()-self.started >= .8:
            self.entry_tick = 0
            return False
        return True

    def draw_field(self, area, cr, width, height):
        progress = min(1, (time.monotonic()-self.started)/.8)
        progress = 1-(1-progress)**3
        ledger = self.demo if self.preview else self.service.ledger
        rows = (("AWAKE BATTERY", ledger.awake_wh, ledger.awake_intervals, (.43,.91,.79)),
                ("CPU PACKAGE", ledger.cpu_wh, ledger.cpu_seconds, (.63,.72,.94)),
                ("SLEEP / RESUME", ledger.sleep_wh, ledger.sleep_intervals, (.81,.70,.87)))
        scale = max([abs(row[1]) for row in rows]+[.0001])
        for index, (label, value, measured, rgb) in enumerate(rows):
            y = 13+index*30
            cr.set_font_size(9)
            cr.set_source_rgba(*rgb,.85)
            cr.move_to(0,y)
            cr.show_text(label)
            text = wh(value) if measured else "Waiting"
            ext = cr.text_extents(text)
            cr.move_to(width-ext.width,y)
            cr.show_text(text)
            cr.set_line_width(1)
            cr.set_source_rgba(*rgb,.10)
            cr.move_to(0,y+9); cr.line_to(width,y+9); cr.stroke()
            if not measured or value <= 0:
                continue
            end = max(1, width*value/scale*progress)
            gradient = cairo.LinearGradient(0,0,end,0)
            gradient.add_color_stop_rgba(0,*rgb,.12)
            gradient.add_color_stop_rgba(.8,*rgb,.8)
            gradient.add_color_stop_rgba(1,*rgb,.5)
            cr.set_source(gradient)
            cr.set_line_width(2)
            cr.move_to(0,y+9); cr.line_to(end,y+9); cr.stroke()
            cr.set_source_rgba(*rgb,.9)
            cr.arc(end,y+9,2,0,6.2832); cr.fill()

    def refresh(self):
        ledger = self.demo if self.preview else self.service.ledger
        total_intervals = ledger.awake_intervals+ledger.sleep_intervals
        total_wh = ledger.awake_wh+ledger.sleep_wh
        self.labels["total"].set_text(wh(total_wh) if total_intervals else "Listening to your battery")
        self.field.queue_draw()
        if total_intervals:
            pp = ledger.awake_pp+ledger.sleep_pp
            pp_complete = ledger.pp_intervals+ledger.sleep_pp_intervals == total_intervals
            percentage = f"{pp:.1f} percentage points decrease" if pp_complete else "Percentage change unavailable for some intervals"
            self.labels["battery"].set_text(f"Measured battery decrease · {percentage}\nAwake: {wh(ledger.awake_wh)} over {duration(ledger.awake_seconds)}")
        else:
            self.labels["battery"].set_text("Battery change appears after two on-battery samples.\nSmall changes may be below the battery gauge resolution.")
        cpu = f"CPU package · {wh(ledger.cpu_wh)} over {duration(ledger.cpu_seconds)}" if ledger.cpu_seconds else "CPU package · collecting on-battery readings"
        if ledger.live_cpu_w is not None:
            cpu += f"\nLive package power · {ledger.live_cpu_w:.2f} W"
            if not self.preview and self.service.ledger.previous.external is True:
                cpu += " · on external power"
        self.labels["cpu"].set_text(cpu)
        sleep = f"Sleep / resume · {wh(ledger.sleep_wh)} over {duration(ledger.sleep_seconds)}" if ledger.sleep_intervals else "Sleep / resume · no measured interval yet"
        self.labels["sleep"].set_text(sleep+(f" · {ledger.sleep_pp:.1f} pp decrease" if ledger.sleep_pp_intervals else "")+"\nNo CPU attribution here. Includes sampling edges and 30 s resume settling; charging while asleep may be unobserved.")
        status = ledger.last_interval
        if not self.preview and self.service.ledger.previous.external is True:
            status = "External power · unplug to measure battery loss. Live CPU readings still work."
        self.labels["status"].set_text(status)
        self.labels["coverage"].set_text(f"Battery gaps: {ledger.gaps} · CPU gaps: {ledger.counter_gaps}\n2 s samples while open · 15 s on battery when closed · memory only")

    def on_close(self, *_):
        if self.entry_tick:
            self.field.remove_tick_callback(self.entry_tick)
            self.entry_tick = 0
        self.service.set_visible(False)
        return False
