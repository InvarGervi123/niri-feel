"""Ambient edge haze first; a tiny intent-driven action strip second."""
import math
import time
import cairo
from gi.repository import Gtk, Gdk, GLib
from .visual import Layer
from .render import smooth

GLOW_DURATION=3.2
PREVIEW_GLOW_DURATION=6.0
OPTIONS_VISIBLE_SECONDS=8.0


def render_glow(cr,width,height,elapsed,duration=GLOW_DURATION):
    alpha=smooth(elapsed/.85)*(1-smooth((elapsed-(duration-1.45))/1.45))
    if alpha<=0:
        return
    depth=min(128,min(width,height)*.18)
    rose=(.96,.29,.34)
    edges=((0,depth,(0,0,depth,height),True),
           (width,width-depth,(width-depth,0,depth,height),True),
           (0,depth,(0,0,width,depth),False),
           (height,height-depth,(0,height-depth,width,depth),False))
    for start,end,rect,vertical in edges:
        gradient=(cairo.LinearGradient(start,0,end,0) if vertical
                  else cairo.LinearGradient(0,start,0,end))
        strength=.30 if vertical else .23
        gradient.add_color_stop_rgba(0,*rose,strength*alpha)
        gradient.add_color_stop_rgba(.28,*rose,strength*.60*alpha)
        gradient.add_color_stop_rgba(.65,*rose,strength*.16*alpha)
        gradient.add_color_stop_rgba(1,*rose,0)
        cr.set_source(gradient); cr.rectangle(*rect); cr.fill()
    # A few broad drifting plumes, clipped to the edge bands. No screen-wide wash.
    drift=math.sin(elapsed*.65)*12
    plumes=((0,height*.30+drift,depth, min(220,height*.32),(0,0,depth,height)),
            (width,height*.68-drift,depth,min(240,height*.32),(width-depth,0,depth,height)),
            (width*.70-drift,0,min(260,width*.30),depth,(0,0,width,depth)),
            (width*.35+drift,height,min(260,width*.30),depth,(0,height-depth,width,depth)))
    for x,y,rx,ry,rect in plumes:
        cr.save(); cr.rectangle(*rect); cr.clip()
        cr.translate(x,y); cr.scale(rx,ry)
        mist=cairo.RadialGradient(0,0,0,0,0,1)
        mist.add_color_stop_rgba(0,*rose,.10*alpha)
        mist.add_color_stop_rgba(.45,*rose,.035*alpha)
        mist.add_color_stop_rgba(1,*rose,0)
        cr.set_source(mist); cr.rectangle(-1,-1,2,2); cr.fill()
        cr.restore()


class LowWindow(Gtk.ApplicationWindow):
    def __init__(self,app,monitor,controller,with_card):
        super().__init__(application=app,title="Niri Feel · Low battery")
        self.controller=controller
        self.card=None
        self.intent=False
        self.handle=None
        self.handle_revealer=None
        self.sources=set()
        self.stopped=False
        self.tick_id=0
        self.input_tick=0
        self.input_until=0.0
        self.input_bounds=None
        self.glow_duration=PREVIEW_GLOW_DURATION if controller.preview else GLOW_DURATION
        self.started=time.monotonic()
        self.set_decorated(False)
        self.set_focusable(False)
        self.set_can_focus(False)
        Layer.init_for_window(self)
        Layer.set_namespace(self,"niri-feel-low")
        Layer.set_monitor(self,monitor)
        Layer.set_layer(self,Layer.Layer.OVERLAY)
        for edge in (Layer.Edge.TOP,Layer.Edge.BOTTOM,Layer.Edge.LEFT,Layer.Edge.RIGHT):
            Layer.set_anchor(self,edge,True)
        Layer.set_exclusive_zone(self,-1)
        Layer.set_keyboard_mode(self,Layer.KeyboardMode.NONE)
        root=Gtk.Overlay()
        self.area=Gtk.DrawingArea()
        self.area.set_draw_func(lambda area,cr,w,h:render_glow(cr,w,h,time.monotonic()-self.started,self.glow_duration))
        self.area.set_can_target(False)
        root.set_child(self.area)
        self.set_child(root)
        if with_card:
            self.card=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=7)
            self.card.add_css_class("low-strip")
            self.card.set_halign(Gtk.Align.CENTER)
            self.card.set_valign(Gtk.Align.END)
            self.card.set_margin_bottom(34)
            self.card.set_visible(False)
            root.add_overlay(self.card)
            self.handle_revealer=Gtk.Revealer()
            self.handle_revealer.set_can_target(False)
            self.handle_revealer.set_transition_type(Gtk.RevealerTransitionType.CROSSFADE)
            self.handle_revealer.set_transition_duration(350)
            self.handle_revealer.set_halign(Gtk.Align.CENTER)
            self.handle_revealer.set_valign(Gtk.Align.END)
            self.handle_revealer.set_margin_bottom(42)
            self.handle=Gtk.Button(label="Options")
            self.handle.add_css_class("low-handle")
            self.handle.set_focus_on_click(False)
            self.handle.set_size_request(100,34)
            self.handle.set_cursor_from_name("pointer")
            self.handle.connect("clicked",lambda _:self.later(0,controller.reveal))
            self.handle_revealer.set_child(self.handle)
            root.add_overlay(self.handle_revealer)
            self.handle_revealer.connect("notify::child-revealed",lambda *_:self.sync_input())
            # The aura stays untouched. The labelled control arrives only as its
            # fade begins, then remains available for eight seconds if ignored.
            self.later(round((self.glow_duration-1.45)*1000),self.arm_handle)
        self.connect("realize",lambda *_:self.get_surface().set_input_region(cairo.Region()))
        self.connect("map",lambda *_:self.sync_input())
        self.tick_id=self.area.add_tick_callback(self.tick)
        self.set_visible(True)

    def later(self,ms,callback):
        def fire():
            self.sources.discard(timer)
            if not self.stopped:
                callback()
            return False
        timer=GLib.timeout_add(ms,fire)
        self.sources.add(timer)

    def arm_handle(self):
        if not self.intent:
            self.handle_revealer.set_can_target(True)
            self.handle_revealer.set_reveal_child(True)
            self.sync_input()
            self.later(round(OPTIONS_VISIBLE_SECONDS*1000),self.fade_handle)

    def fade_handle(self):
        if not self.intent and self.handle_revealer:
            self.handle_revealer.set_can_target(False)
            self.handle_revealer.set_reveal_child(False)
            self.sync_input()

    def tick(self,widget,clock):
        self.input_region()
        self.area.queue_draw()
        if time.monotonic()-self.started>=self.glow_duration:
            self.tick_id=0
            return False
        return True

    def sync_input(self):
        if self.stopped:
            return
        # GTK may allocate a revealer after the aura frame callback has stopped.
        # Follow that short transition instead of sampling zero-sized bounds once.
        self.input_until=time.monotonic()+.5
        self.input_region()
        if not self.input_tick:
            self.input_tick=self.add_tick_callback(self.input_frame)

    def input_frame(self,widget,clock):
        self.input_region()
        if self.stopped or time.monotonic()>=self.input_until:
            self.input_tick=0
            return False
        return True

    def input_region(self):
        surface=self.get_surface()
        if not surface:
            return False
        rect=None
        target=(self.card if self.intent else
                self.handle if self.handle_revealer and self.handle_revealer.get_reveal_child() else None)
        if target is not None and target.get_visible():
            ok,bounds=target.compute_bounds(self)
            if ok and bounds.get_width()>0 and bounds.get_height()>0:
                x=math.floor(bounds.get_x()); y=math.floor(bounds.get_y())
                rect=(x,y,math.ceil(bounds.get_x()+bounds.get_width())-x,
                      math.ceil(bounds.get_y()+bounds.get_height())-y)
        if rect!=self.input_bounds:
            region=cairo.Region()
            if rect is not None:
                region.union(cairo.RectangleInt(*rect))
            surface.set_input_region(region)
            self.input_bounds=rect
            # wl_surface input regions are double-buffered. A redraw commits
            # the new region even when the six-second aura has stopped drawing.
            self.area.queue_draw()
        return False

    def show_card(self,title,body,buttons):
        if not self.card:
            return
        self.intent=True
        # A hidden Gtk.Revealer still has an allocation. It must stop participating
        # in GTK picking, or it intercepts center buttons such as Brightness.
        self.handle_revealer.set_can_target(False)
        self.handle_revealer.set_reveal_child(False)
        self.card.set_visible(True)
        child=self.card.get_first_child()
        while child:
            following=child.get_next_sibling()
            self.card.remove(child); child=following
        if title:
            heading=Gtk.Label(label=title,xalign=.5)
            heading.add_css_class("low-heading")
            self.card.append(heading)
        if body:
            label=Gtk.Label(label=body,xalign=.5)
            label.set_wrap(True)
            label.set_max_width_chars(40)
            label.set_justify(Gtk.Justification.CENTER)
            label.add_css_class("low-body")
            self.card.append(label)
        row=Gtk.Box(spacing=5)
        row.set_halign(Gtk.Align.CENTER)
        for caption,callback in buttons:
            button=Gtk.Button(label=caption)
            button.set_focus_on_click(False)
            button.connect("clicked",lambda _,callback=callback:self.later(0,callback))
            row.append(button)
        self.card.append(row)
        self.sync_input()

    def stop(self):
        self.stopped=True
        for timer in self.sources:
            GLib.source_remove(timer)
        self.sources.clear()
        if self.input_tick:
            self.remove_tick_callback(self.input_tick)
            self.input_tick=0
        if self.tick_id:
            self.area.remove_tick_callback(self.tick_id)
            self.tick_id=0
        self.destroy()


def install_style(display):
    css=Gtk.CssProvider()
    css.load_from_data(b"""
    .low-strip { background: transparent; border: none; padding: 8px 12px; }
    .low-heading { color: #eab5bb; font-size: 11px; text-shadow: 0 1px 3px #091316; }
    .low-body { color: #d5e8e1; font-size: 12px; text-shadow: 0 1px 3px #091316; }
    .low-strip button { background: rgba(15,31,34,.68); color: #baf2dd; border: none;
                       border-radius: 14px; padding: 6px 12px; box-shadow: none; }
    .low-strip button:hover { background: rgba(36,70,65,.85); }
    .low-handle { background: rgba(17,31,35,.74); color: #edc8cd;
                  border: 1px solid rgba(234,153,166,.30); border-radius: 18px;
                  padding: 6px 17px; font-size: 12px; box-shadow: none; }
    .low-handle:hover { background: rgba(31,53,55,.90); color: #d0f2e5; }
    """)
    Gtk.StyleContext.add_provider_for_display(display,css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION+1)
