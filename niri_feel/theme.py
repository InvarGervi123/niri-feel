"""Shared Niri Feel palette and GTK style registration."""
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

MINT = (.55, .94, .81)
PALE = (.93, .98, .96)
MUTED = (.72, .82, .81)
ROSE = (.92, .69, .73)

COLORS = {
    "ink": "#031011",
    "surface": "rgba(3, 16, 17, .91)",
    "surface-soft": "rgba(9, 28, 30, .28)",
    "mint": "#8ceacf",
    "pale": "#edf9f5",
    "value": "#b8f4df",
    "copy": "#d3e6df",
    "muted": "#b8d1ca",
    "note": "#adc6be",
    "border": "rgba(140, 234, 207, .18)",
}

BASE_CSS = f"""
window {{ background: transparent; box-shadow: none; }}
.feel-surface {{ background: {COLORS['surface']}; border: 1px solid {COLORS['border']}; border-radius: 12px; box-shadow: 0 0 18px rgba(140,234,207,.11); }}
.feel-brightness {{ padding: 7px 10px; min-width: 124px; }}
.feel-brightness label {{ font-family: sans-serif; text-shadow: 0 1px 2px rgba(3,12,16,.8); }}
.feel-brightness .feel-value {{ color: {COLORS['pale']}; font-size: 17px; font-weight: 500; }}
.feel-brightness .feel-muted {{ color: {COLORS['muted']}; font-size: 10px; }}
.feel-brightness progressbar {{ min-height: 3px; }}
.feel-brightness progressbar trough {{ min-height: 3px; background: rgba(140,234,207,.12); border-radius: 3px; }}
.feel-brightness progressbar progress {{ min-height: 3px; background: {COLORS['mint']}; border-radius: 3px; transition: all 180ms ease; }}
"""


def install_css(display, css, priority=Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 2):
    provider = Gtk.CssProvider()
    stylesheet = css.decode() if isinstance(css, bytes) else css
    if hasattr(provider, 'load_from_string'):
        provider.load_from_string(stylesheet)
    else:
        provider.load_from_data(stylesheet.encode())
    Gtk.StyleContext.add_provider_for_display(display, provider, priority)
    return provider
