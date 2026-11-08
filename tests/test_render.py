import unittest
import cairo
from niri_feel.render import render

class RenderTests(unittest.TestCase):
    def test_animation_is_finite_and_both_paths_render(self):
        for kind in ("connect", "disconnect"):
            for width in (360, 1920, 3840):
                for t in (0, .2, .7, 1.2, 2.4, 3.4):
                    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, 108)
                    render(cairo.Context(surface), width, 108, t, kind,
                           "Power connected", "Preview · Fully charged · 100%")
                    surface.flush()
                    has_pixels = any(surface.get_data())
                    self.assertEqual(has_pixels, 0 < t < 3.4, (kind, width, t))

if __name__ == "__main__":
    unittest.main()
