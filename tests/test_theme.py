import unittest
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
from niri_feel.theme import BASE_CSS, MINT, PALE, MUTED


class ThemeTests(unittest.TestCase):
    def test_shared_brightness_stylesheet_parses(self):
        provider = Gtk.CssProvider()
        provider.load_from_string(BASE_CSS)

    def test_summary_palette_tokens_are_shared(self):
        from niri_feel import session_visual
        self.assertEqual(session_visual.MINT, MINT)
        self.assertEqual(session_visual.PALE, PALE)
        self.assertEqual(session_visual.MUTED, MUTED)


if __name__ == '__main__':
    unittest.main()
