"""Reuse Niri Feel's edge haze and tested Wayland input-region handling."""
import unicodedata
import time
import cairo
from gi.repository import Gtk, Gdk, Pango
from .low_visual import LowWindow, render_glow
from .floating_ui import LightColumn, Glyph, text_label, actions, install_style as install_shared_style

AURA_SECONDS=3.2


def render_network_glow(cr,width,height,elapsed,kind):
    # Reuse only the alpha field; existing low-battery colors/rendering stay intact.
    cr.push_group_with_content(cairo.CONTENT_ALPHA)
    render_glow(cr,width,height,elapsed,AURA_SECONDS)
    mask=cr.pop_group()
    color=(.98,.68,.25) if kind=="offline" else (.43,.91,.69)
    cr.set_source_rgb(*color); cr.mask(mask)


def clean(value):
    return "".join(c if c.isprintable() and unicodedata.category(c)!="Cf" else "�" for c in str(value))


def size_label(value):
    if value is None: return "Unavailable"
    for suffix in ("B","KiB","MiB","GiB","TiB"):
        if value<1024 or suffix=="TiB":
            return f"{value:.1f} {suffix}" if suffix!="B" else f"{value:.0f} B"
        value/=1024


class NetworkWindow(LowWindow):
    def __init__(self,app,monitor,controller,kind):
        super().__init__(app,monitor,controller,False,namespace="niri-feel-network")
        self.network_monitor=monitor
        self.set_title("Niri Feel · Network Recovery")
        self.glow_duration=AURA_SECONDS
        self.network_kind=kind
        self.area.set_draw_func(self.draw_network_surface)
        self.recovery_revealer=Gtk.Revealer()
        self.recovery_revealer.set_transition_type(Gtk.RevealerTransitionType.CROSSFADE)
        self.recovery_revealer.set_transition_duration(450)
        self.recovery_revealer.set_halign(Gtk.Align.CENTER)
        self.recovery_revealer.set_valign(Gtk.Align.END)
        self.recovery_revealer.set_margin_bottom(30)
        self.recovery_revealer.set_can_target(False)
        self.card=LightColumn(self.area.queue_draw)
        self.card.add_css_class("network-sheet")
        self.card.set_size_request(380,-1)
        self.recovery_revealer.set_child(self.card)
        self.get_child().add_overlay(self.recovery_revealer)
        self.recovery_revealer.connect("notify::child-revealed",lambda *_:self.sync_input())

    def draw_network_surface(self,area,cr,width,height):
        render_network_glow(cr,width,height,time.monotonic()-self.started,self.network_kind)
        self.draw_content_light(cr)

    def show_item(self,item,index,count,tip):
        self.intent=True
        child=self.card.get_first_child()
        while child:
            after=child.get_next_sibling(); self.card.remove(child); child=after
        self.light_visible=True
        def label(value,style,truncate=False):
            widget=text_label(clean(value),style,truncate,chars=46)
            self.card.append(widget);return widget
        label("PREVIEW · SIMULATED" if self.controller.preview else "NETWORK RESTORED","feel-eyebrow")
        heading=Gtk.Box(spacing=7);heading.set_halign(Gtk.Align.CENTER)
        heading.append(Glyph('file',20))
        heading.append(text_label(clean((item.partial.payload or item.partial.marker).name),'feel-title',True,38))
        self.card.append(heading)
        if item.partial.kind=="aria2":
            label(f"Control: {item.partial.marker.name}","feel-note",True)
        metrics=Gtk.Box(spacing=26);metrics.set_halign(Gtk.Align.CENTER)
        for kind,value,caption in (('download',item.partial.allocated,'Allocated on disk'),('file',item.partial.length,'File length')):
            column=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=0)
            line=Gtk.Box(spacing=5);line.set_halign(Gtk.Align.CENTER)
            line.append(Glyph(kind,18));line.append(text_label(size_label(value),'feel-value'))
            column.append(line);column.append(text_label(caption,'feel-note'));metrics.append(column)
        self.card.append(metrics)
        label(item.partial.marker.parent,"feel-muted",True)
        label(item.status,"feel-status")
        label(tip,"feel-muted")
        note=("Payload unavailable · control file only." if item.partial.kind=="aria2" and item.partial.payload is None
              else "File sizes are not verified download progress.")
        self.note=label(note,"feel-note")
        self.note.connect('notify::label',lambda *_:self.sync_input())
        buttons=[("Open folder",self.controller.open_folder)]
        if count>1:buttons.append((f"Next · {index+1}/{count}",self.controller.next_item))
        buttons.append(("Dismiss",self.controller.dismiss))
        for row in actions(buttons,lambda callback:self.later(0,callback)):
            self.card.append(row)
        self.card.animate(duration=.4)
        self.recovery_revealer.set_can_target(True)
        self.recovery_revealer.set_reveal_child(True)
        self.sync_input()

    def fade_help(self):
        self.intent=False
        self.card.animate(appearing=False,duration=.45)
        self.recovery_revealer.set_can_target(False)
        self.recovery_revealer.set_reveal_child(False)
        self.sync_input()


def install_style(display):
    install_shared_style(display)
