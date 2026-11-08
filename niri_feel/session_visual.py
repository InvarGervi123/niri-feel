"""A reconnect story on the existing click-through edge surface."""
import cairo
from .render import smooth

SUMMARY_DURATION = 8.0


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


def render_summary(cr,width,height,elapsed,summary):
    alpha=smooth((elapsed-.45)/.65)*(1-smooth((elapsed-6.8)/1.2))
    if alpha <= 0:
        return
    cx=width/2
    top=height-254+7*(1-smooth((elapsed-.45)/.65))
    scale=min(1,(width-24)/520)
    cr.save()
    cr.translate(cx,top); cr.scale(scale,scale)
    # Soft light/shade field, no notification frame or opaque panel.
    halo=cairo.RadialGradient(0,112,35,0,112,290)
    halo.add_color_stop_rgba(0,.015,.04,.045,.85*alpha)
    halo.add_color_stop_rgba(.65,.015,.04,.045,.62*alpha)
    halo.add_color_stop_rgba(1,.015,.04,.045,0)
    cr.set_source(halo); cr.rectangle(-300,-40,600,300); cr.fill()
    mint=(.55,.94,.81); pale=(.93,.98,.96); muted=(.72,.82,.81)
    label="PREVIEW · SIMULATED BATTERY SESSION" if summary.get("preview") else "BACK ON POWER"
    text(cr,label,0,8,10,mint,alpha)
    text(cr,"Your battery session.",0,36,20,pale,alpha)
    # Three honest endpoint metrics. Unknown readings never become zero.
    wh=summary.get("wh")
    percent=summary.get("percentage_points")
    elapsed_time=summary.get("duration")
    metrics=((f"{wh:.3f} Wh" if wh is not None else "Unknown", "net battery decrease"),
             (f"{percent:.1f} pp" if percent is not None else "Unknown", "percentage-point drop"),
             (duration(elapsed_time), "session span" if summary.get("interrupted") else ("on battery" if summary.get("start_observed") else "observed on battery")))
    for x,(value,caption) in zip((-176,0,176),metrics):
        text(cr,value,x,78,23,pale,alpha)
        text(cr,caption,x,99,10,muted,alpha)
    active=summary.get("active_seconds",0); sleep=summary.get("sleep_seconds",0); gap=summary.get("unknown_seconds",0)
    total=active+sleep+gap
    left=-244
    if total>0:
        for seconds,color in ((active,mint),(sleep,(.65,.72,.94)),(gap,(.89,.73,.50))):
            length=488*seconds/total
            if length>0:
                cr.set_source_rgba(*color,.7*alpha)
                cr.set_line_width(2)
                cr.move_to(left,119); cr.line_to(left+length,119); cr.stroke()
            left+=length
    timing=f"Active {duration(active)}   ·   Sleep {duration(sleep)}   ·   Uncovered {duration(gap)}"
    if summary.get("unknown_duration"):
        timing="Known time only · elapsed time across reboot unavailable"
    text(cr,timing,0,140,11,muted,alpha)
    cpu=summary.get("cpu_wh")
    cpu_text=f"CPU package  {cpu:.3f} Wh · {duration(summary.get('cpu_seconds',0))} measured" if cpu is not None else "CPU package · insufficient measured coverage"
    text(cr,cpu_text,0,165,13,mint,alpha)
    notes=summary.get("notes",[])
    if wh is None and summary.get("measured_wh") is not None:
        notes=[f"Measured intervals only: {summary['measured_wh']:.3f} Wh"]+notes
    if summary.get("cpu_gaps") or summary.get("battery_gaps"):
        notes=[f"Coverage gaps · battery {summary.get('battery_gaps',0)} / CPU {summary.get('cpu_gaps',0)}"]+notes
    # Surface the most consequential uncertainty, with a concise second line.
    if notes:
        text(cr,notes[0],0,188,10,(.9,.79,.61),alpha)
        if len(notes)>1:
            text(cr,notes[1],0,204,10,(.9,.79,.61),alpha)
    else:
        text(cr,"CPU measured while awake · resume settling excluded",0,188,10,muted,alpha)
    text(cr,"Screen · SSD · RAM: not independently measured",0,224,10,muted,alpha*.9)
    cr.restore()
