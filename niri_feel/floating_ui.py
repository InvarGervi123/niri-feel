"""Shared floating typography, vector actions and light fields for Niri Feel."""
import math
import time
import cairo
import gi
gi.require_version('Gtk','4.0')
from gi.repository import Gtk, Pango
from .render import smooth
from .session_visual import icon as summary_icon

MINT=(.55,.94,.81)
PALE=(.93,.98,.96)
MUTED=(.72,.82,.81)
ROSE=(.92,.69,.73)
_STYLED=set()


def paint_field(cr,x,y,width,height,alpha=1):
    """An unframed elliptical shade, painted on the whole layer, not a card."""
    if alpha<=0 or width<=0 or height<=0: return
    cr.save()
    cr.translate(x+width/2,y+height/2)
    cr.scale(max(70,width*.74),max(38,height*.88))
    shade=cairo.RadialGradient(0,0,.05,0,0,1)
    shade.add_color_stop_rgba(0,.015,.04,.045,.85*alpha)
    shade.add_color_stop_rgba(.60,.015,.04,.045,.67*alpha)
    shade.add_color_stop_rgba(.84,.015,.04,.045,.23*alpha)
    shade.add_color_stop_rgba(1,.015,.04,.045,0)
    cr.set_source(shade); cr.rectangle(-1,-1,2,2); cr.fill()
    cr.restore()


def draw_glyph(cr,kind,size=20,color=MINT):
    cr.save(); cr.translate(size/2,size/2); cr.scale(size/28,size/28)
    if kind in ('battery','cpu','energy'):
        summary_icon(cr,kind,0,0,color,1)
    else:
        cr.set_source_rgb(*color); cr.set_line_width(1.6)
        cr.set_line_cap(cairo.LINE_CAP_ROUND); cr.set_line_join(cairo.LINE_JOIN_ROUND)
        if kind=='brightness':
            cr.arc(0,0,4.5,0,math.tau); cr.stroke()
            for angle in range(8):
                a=angle*math.pi/4
                cr.move_to(math.cos(a)*8,math.sin(a)*8);cr.line_to(math.cos(a)*11,math.sin(a)*11)
            cr.stroke()
        elif kind in ('folder','file'):
            if kind=='folder':
                cr.move_to(-10,-6);cr.line_to(-3,-6);cr.line_to(0,-3);cr.line_to(10,-3)
                cr.line_to(8,8);cr.line_to(-9,8);cr.close_path()
            else:
                cr.move_to(-7,-10);cr.line_to(3,-10);cr.line_to(8,-5);cr.line_to(8,10)
                cr.line_to(-7,10);cr.close_path();cr.move_to(3,-10);cr.line_to(3,-5);cr.line_to(8,-5)
            cr.stroke()
        elif kind=='download':
            cr.move_to(0,-10);cr.line_to(0,4);cr.move_to(-5,0);cr.line_to(0,5);cr.line_to(5,0)
            cr.move_to(-9,5);cr.line_to(-9,10);cr.line_to(9,10);cr.line_to(9,5);cr.stroke()
        elif kind=='dismiss':
            cr.move_to(-5,-5);cr.line_to(5,5);cr.move_to(5,-5);cr.line_to(-5,5);cr.stroke()
        elif kind=='replay':
            cr.arc(0,0,8,-.6,4.8);cr.stroke();cr.move_to(0,-12);cr.line_to(1,-7);cr.line_to(-4,-7);cr.stroke()
        elif kind in ('next','back'):
            d=-1 if kind=='back' else 1
            cr.move_to(-4*d,-7);cr.line_to(4*d,0);cr.line_to(-4*d,7);cr.stroke()
        elif kind=='apply':
            cr.move_to(-8,0);cr.line_to(-2,6);cr.line_to(9,-7);cr.stroke()
        else:
            for x in (-6,0,6): cr.arc(x,0,1.3,0,math.tau);cr.fill()
    cr.restore()


class Glyph(Gtk.DrawingArea):
    def __init__(self,kind,size=20,color=MINT):
        super().__init__();self.set_content_width(size);self.set_content_height(size)
        self.set_can_target(False)
        self.set_draw_func(lambda area,cr,w,h:draw_glyph(cr,kind,size,color))


class LightButton(Gtk.Button):
    def __init__(self,caption,kind=None):
        super().__init__()
        self.caption=caption
        self.add_css_class('feel-action');self.set_focus_on_click(False)
        self.set_cursor_from_name('pointer')
        self.update_property([Gtk.AccessibleProperty.LABEL],[caption])
        row=Gtk.Box(spacing=5);row.set_halign(Gtk.Align.CENTER)
        kind=kind or action_icon(caption)
        row.append(Glyph(kind,16))
        title=Gtk.Label(label=caption);title.add_css_class('feel-button-text');row.append(title)
        self.set_child(row)

    def get_label(self):
        return self.caption


def action_icon(caption):
    for prefix,kind in (('Performance','cpu'),('Brightness','brightness'),('Open folder','folder'),
                        ('Next','next'),('Back','back'),('Replay','replay'),('Apply','apply'),
                        ('Simulate apply','apply'),('Cancel','back'),('Dismiss','dismiss')):
        if caption.startswith(prefix): return kind
    return 'more'


def text_label(value,style='feel-copy',truncate=False,chars=43):
    label=Gtk.Label(label=str(value),xalign=.5)
    label.add_css_class(style);label.set_max_width_chars(chars)
    label.set_justify(Gtk.Justification.CENTER)
    if truncate:
        label.set_ellipsize(Pango.EllipsizeMode.MIDDLE);label.set_tooltip_text(str(value))
    else:label.set_wrap(True)
    return label


def actions(buttons,dispatch):
    """All actions stay labelled; Preview's fourth action gets a second short row."""
    rows=[]
    groups=[buttons] if len(buttons)<=3 else [buttons[:2],buttons[2:]]
    for group in groups:
        row=Gtk.Box(spacing=7);row.set_halign(Gtk.Align.CENTER)
        for caption,callback in group:
            button=LightButton(caption)
            button.connect('clicked',lambda _,callback=callback:dispatch(callback))
            row.append(button)
        rows.append(row)
    return rows


class LightColumn(Gtk.Box):
    def __init__(self,redraw):
        super().__init__(orientation=Gtk.Orientation.VERTICAL,spacing=7)
        self.add_css_class('feel-content');self.redraw=redraw;self.motion=0
        self.connect('unmap',lambda *_:self.stop_motion())

    def animate(self,appearing=True,duration=.28):
        self.stop_motion();started=time.monotonic();start=0 if appearing else self.get_opacity()
        self.set_opacity(start)
        def frame(widget,clock):
            t=min(1,(time.monotonic()-started)/duration)
            self.set_opacity(smooth(t) if appearing else start*(1-smooth(t)))
            self.redraw()
            if t>=1:self.motion=0;return False
            return True
        self.motion=self.add_tick_callback(frame)

    def stop_motion(self):
        if self.motion:self.remove_tick_callback(self.motion);self.motion=0


def install_style(display):
    if display in _STYLED:return
    _STYLED.add(display)
    css=Gtk.CssProvider()
    css.load_from_data(b"""
    .feel-content { background: transparent; border: none; padding: 12px 18px; }
    .feel-content label, .feel-button-text {
      font-family: sans-serif; font-weight: 400; color: #edf9f5;
      text-shadow: -1px 0 rgba(3,12,16,.8), 1px 0 rgba(3,12,16,.8),
                   0 -1px rgba(3,12,16,.8), 0 1px rgba(3,12,16,.9), 0 2px 3px rgba(3,12,16,.7);
    }
    .feel-content .feel-eyebrow { color: #8ceacf; font-size: 10px; letter-spacing: 1px; }
    .feel-content .feel-title { color: #edf9f5; font-size: 16px; }
    .feel-content .feel-value { color: #b8f4df; font-size: 22px; }
    .feel-content .feel-copy { color: #d3e6df; font-size: 12px; }
    .feel-content .feel-muted { color: #b8d1ca; font-size: 11px; }
    .feel-content .feel-note { color: #adc6be; font-size: 10px; }
    .feel-content .feel-status { color: #e0c79f; font-size: 11px; }
    .feel-action { background: rgba(9,28,30,.28); color: #baf2dd;
                   border: 1px solid rgba(140,234,207,.17); border-radius: 15px;
                   padding: 6px 10px; box-shadow: none; }
    .feel-action .feel-button-text { color: #d4f8ea; font-size: 11px; }
    .feel-action:hover { background: rgba(22,54,50,.58); border-color: rgba(140,234,207,.48); }
    .feel-action:active { background: rgba(35,74,65,.7); }
    """)
    Gtk.StyleContext.add_provider_for_display(display,css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION+2)
