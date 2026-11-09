"""A reconnect story on the existing click-through edge surface."""
import cairo
from .render import smooth

SUMMARY_DURATION = 4.8
SUMMARY_HEIGHT = 210
SUMMARY_WIDTH = 380


def duration(seconds):
    if seconds is None:
        return "Unknown"
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds/60:.0f}m"
    return f"{seconds/3600:.1f}h"


def text(cr, value, x, y, size, color, alpha, centered=True):
    cr.select_font_face("sans-serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    cr.set_font_size(size)
    ext=cr.text_extents(value)
    if centered:
        x -= ext.width/2+ext.x_bearing
    for dx,dy in ((-1,0),(1,0),(0,-1),(0,1)):
        cr.set_source_rgba(.01,.025,.03,.45*alpha)
        cr.move_to(x+dx,y+dy); cr.show_text(value)
    cr.set_source_rgba(*color,alpha)
    cr.move_to(x,y); cr.show_text(value)


def icon(cr, kind, x, y, color, alpha):
    """Small vector paths, independent of icon fonts or external assets."""
    cr.save()
    cr.translate(x,y)
    cr.set_source_rgba(*color,alpha)
    cr.set_line_width(1.6)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    if kind == "battery":
        cr.move_to(-9,-7); cr.line_to(7,-7)
        cr.curve_to(9,-7,10,-6,10,-4)
        cr.line_to(10,4); cr.curve_to(10,6,9,7,7,7)
        cr.line_to(-9,7); cr.curve_to(-11,7,-12,6,-12,4)
        cr.line_to(-12,-4); cr.curve_to(-12,-6,-11,-7,-9,-7)
        cr.close_path(); cr.stroke()
        cr.move_to(13,-2); cr.line_to(13,2); cr.stroke()
        for left in (-7,-2,3):
            cr.move_to(left,-3); cr.line_to(left,3)
        cr.stroke()
    elif kind == "energy":
        cr.move_to(2,-11); cr.line_to(-7,1); cr.line_to(0,1)
        cr.line_to(-2,11); cr.line_to(8,-2); cr.line_to(1,-2)
        cr.close_path(); cr.stroke()
    else:
        cr.rectangle(-8,-8,16,16); cr.stroke()
        cr.rectangle(-3,-3,6,6); cr.stroke()
        for offset in (-4,4):
            for start,end in (((offset,-12),(offset,-8)),((offset,8),(offset,12)),
                              ((-12,offset),(-8,offset)),((8,offset),(12,offset))):
                cr.move_to(*start); cr.line_to(*end)
        cr.stroke()
    cr.restore()


def render_summary(cr,width,height,elapsed,summary):
    alpha=smooth((elapsed-.25)/.5)*(1-smooth((elapsed-3.9)/.9))
    if alpha <= 0:
        return
    cx=width/2
    top=height-185+4*(1-smooth((elapsed-.25)/.5))
    scale=min(1,(width-24)/SUMMARY_WIDTH)
    cr.save()
    cr.translate(cx,top); cr.scale(scale,scale)
    halo=cairo.RadialGradient(0,82,25,0,82,210)
    halo.add_color_stop_rgba(0,.015,.04,.045,.85*alpha)
    halo.add_color_stop_rgba(.65,.015,.04,.045,.62*alpha)
    halo.add_color_stop_rgba(1,.015,.04,.045,0)
    cr.set_source(halo); cr.rectangle(-218,-29,436,218); cr.fill()
    mint=(.55,.94,.81); pale=(.93,.98,.96); muted=(.72,.82,.81)
    label="PREVIEW · SIMULATED" if summary.get("preview") else "BACK ON POWER"
    text(cr,label,0,5,10,mint,alpha)
    metrics=(("battery",summary.get("percentage_points"),"Battery · pp",1),
             ("energy",summary.get("wh"),"Energy · Wh",3),
             ("cpu",summary.get("cpu_wh"),"CPU · Wh",3))
    for x,(kind,value,caption,precision) in zip((-130,0,130),metrics):
        icon(cr,kind,x,36,mint,alpha if value is not None else alpha*.45)
        number=f"{value:.{precision}f}" if value is not None else "—"
        text(cr,number,x,85,30,pale if kind!="cpu" else mint,alpha)
        text(cr,caption,x,105,11,muted,alpha)
    # A decorative light thread, not an inferred component split.
    thread=cairo.LinearGradient(-178,0,178,0)
    thread.add_color_stop_rgba(0,*mint,0)
    thread.add_color_stop_rgba(.5,*mint,.5*alpha)
    thread.add_color_stop_rgba(1,*mint,0)
    cr.set_source(thread); cr.set_line_width(1)
    cr.move_to(-178,119); cr.line_to(178,119); cr.stroke()
    elapsed_time=summary.get("duration")
    span="span" if summary.get("interrupted") else ("on battery" if summary.get("start_observed") else "observed")
    context=[f"{duration(elapsed_time)} {span}" if elapsed_time is not None else "Time unavailable"]
    if summary.get("sleep_seconds",0)>0:
        context.append(f"Sleep {duration(summary['sleep_seconds'])}")
    if summary.get("unknown_seconds",0)>0:
        context.append(f"Gap {duration(summary['unknown_seconds'])}")
    text(cr," · ".join(context),0,140,10,muted,alpha)
    status=[]
    if summary.get("cpu_wh") is not None:
        status.append(f"CPU sampled {duration(summary.get('cpu_seconds',0))}")
    if (summary.get("notes") or summary.get("battery_gaps") or summary.get("cpu_gaps")
            or summary.get("interrupted") or summary.get("unknown_duration")):
        status.append("Partial coverage")
    if any(value is None for _,value,_,_ in metrics):
        status.append("— Not measured")
    if status:
        text(cr," · ".join(status),0,161,10,muted,alpha)
    cr.restore()
