"""Pure Cairo rendering, also testable without a display server."""
import cairo

def clamp(x):
    return max(0.0, min(1.0, x))

def smooth(x):
    x = clamp(x)
    return x*x*(3-2*x)

def render(cr, width, height, elapsed, kind, title, detail):
    t = max(0.0, elapsed)
    opacity = smooth(t/.20) * (1-smooth((t-2.45)/.85))
    if opacity <= 0:
        return
    connected = kind == "connect"
    rgb = (.43, .91, .79) if connected else (.76, .79, .91)
    cx, y = width/2, height-2
    # Connection gathers two travelling streams. Disconnection releases them.
    travel = smooth(t/1.05)
    distance = (1-travel)*width*.43 if connected else travel*width*.43
    if connected:
        strength = opacity * (1-.48*smooth((t-1.0)/.8))
    else:
        strength = opacity * (1-smooth((t-.6)/1.45))
    cr.set_operator(cairo.OPERATOR_OVER)
    for center in (cx-distance, cx+distance):
        radius = 140 + 80*travel
        halo = cairo.RadialGradient(center, y+9, 0, center, y+9, radius)
        halo.add_color_stop_rgba(0, *rgb, .15*strength)
        halo.add_color_stop_rgba(.35, *rgb, .055*strength)
        halo.add_color_stop_rgba(1, *rgb, 0)
        cr.save()
        cr.rectangle(center-radius, height-65, radius*2, 65)
        cr.clip()
        cr.set_source(halo)
        cr.paint()
        cr.restore()
        line = cairo.LinearGradient(center-radius, 0, center+radius, 0)
        for offset, alpha in ((0, 0), (.3, .25), (.5, .9), (.7, .25), (1, 0)):
            line.add_color_stop_rgba(offset, *rgb, alpha*strength)
        cr.set_source(line)
        cr.set_line_width(1.7)
        cr.move_to(center-radius, y)
        cr.line_to(center+radius, y)
        cr.stroke()
    text_alpha = smooth((t-.28)/.35) * (1-smooth((t-2.4)/.75))
    if text_alpha <= 0:
        return
    lift = 5*(1-smooth((t-.28)/.6))
    # Text has a diffuse local shadow, never a notification rectangle.
    for text, size, baseline, color in (
        (title, 15, height-47+lift, (.94,.97,.97)),
        (detail, 11, height-27+lift, (.70,.78,.79))):
        if not text:
            continue
        cr.select_font_face("sans-serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(size)
        ext = cr.text_extents(text)
        x = cx - ext.width/2 - ext.x_bearing
        for dx, dy in ((-1,0),(1,0),(0,-1),(0,1),(0,2)):
            cr.set_source_rgba(.015,.025,.03,.28*text_alpha)
            cr.move_to(x+dx, baseline+dy)
            cr.show_text(text)
        cr.set_source_rgba(*color, text_alpha)
        cr.move_to(x, baseline)
        cr.show_text(text)
