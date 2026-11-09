import tempfile
import os
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch
import cairo
from niri_feel.power import Battery
from niri_feel.low_battery import LowLatch, Capabilities, propose, apply

CAPS=Capabilities(True,"balanced",("balanced","performance","power-saver"),(),"intel_backlight",80,100,True)

class LatchTests(unittest.TestCase):
    def test_crossing_duplicate_and_charger_flapping(self):
        latch=LowLatch()
        self.assertFalse(latch.update(False,Battery(2,16,5,100),100))
        self.assertTrue(latch.update(False,Battery(2,15,5,100),100))
        self.assertFalse(latch.update(False,Battery(2,14,5,101),101))
        self.assertFalse(latch.update(True,Battery(1,15,5,102),102))
        self.assertFalse(latch.update(False,Battery(2,15,5,103),103))
        self.assertFalse(latch.update(True,Battery(1,20,5,104),104))
        self.assertTrue(latch.update(False,Battery(2,15,5,105),105))

    def test_stale_missing_invalid_and_charging_do_not_warn(self):
        for battery in (None,Battery(2,None,5,100),Battery(2,float('nan'),5,100),
                        Battery(2,15,5,0),Battery(1,15,5,100),Battery(2,15,5,200)):
            self.assertFalse(LowLatch().update(False,battery,150))
        self.assertFalse(LowLatch().update(True,Battery(2,15,5,100),100))
        self.assertFalse(LowLatch().update(None,Battery(2,15,5,100),100))

    def test_alert_latch_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'low-battery.json'
            first=LowLatch(path)
            self.assertTrue(first.update(False,Battery(2,15,5,100),100))
            self.assertFalse(LowLatch(path).update(False,Battery(2,14,5,101),101))
            self.assertEqual(path.stat().st_mode & 0o777,0o600)

class ChoiceTests(unittest.TestCase):
    def test_performance_dims_only_after_explicit_confirmation(self):
        port=Mock(); port.read.return_value=CAPS
        proposal=propose('Performance',CAPS)
        self.assertEqual(proposal.target,64)
        self.assertIn('80% to 64%',proposal.explanation)
        with self.assertRaises(ValueError): apply(proposal,port)
        port.read.assert_not_called(); port.set_brightness.assert_not_called()
        apply(proposal,port,confirmed=True)
        port.set_brightness.assert_called_once_with('intel_backlight',64)
        port.set_profile.assert_not_called()

    def test_brightness_uses_supported_saver_without_changing_brightness(self):
        port=Mock(); port.read.return_value=CAPS
        proposal=propose('Brightness',CAPS)
        self.assertIn('CPU performance may decrease',proposal.explanation)
        apply(proposal,port,confirmed=True)
        port.set_profile.assert_called_once_with('power-saver')
        port.set_brightness.assert_not_called()

    def test_preview_cannot_read_or_write_real_settings_even_after_confirm(self):
        port=Mock()
        for choice in ('Performance','Brightness'):
            proposal=propose(choice,CAPS,preview=True)
            self.assertIn('no settings changed',apply(proposal,port,confirmed=True))
        self.assertEqual(port.mock_calls,[])

    def test_external_changes_and_plugging_in_invalidate_confirmation(self):
        for current in (replace(CAPS,on_battery=False),replace(CAPS,profile='performance'),
                        replace(CAPS,brightness=60),replace(CAPS,holds=('other-app',))):
            port=Mock(); port.read.return_value=current
            with self.assertRaises(ValueError): apply(propose('Brightness',CAPS),port,True)
            port.set_profile.assert_not_called(); port.set_brightness.assert_not_called()

    def test_missing_or_held_capabilities_are_not_forced(self):
        for current,choice in ((replace(CAPS,holds=('other-app',)),'Brightness'),
                              (replace(CAPS,profiles=('balanced',)),'Brightness'),
                              (replace(CAPS,profile='power-saver'),'Brightness'),
                              (replace(CAPS,brightness_supported=False),'Performance'),
                              (replace(CAPS,device=None),'Performance'),
                              (replace(CAPS,on_battery=False),'Performance')):
            with self.assertRaises(ValueError): propose(choice,current)

class NoctaliaTests(unittest.TestCase):
    def test_noctalia_default_warning_does_not_overlap_15_percent(self):
        from niri_feel.low_controls import noctalia_owns
        result=Mock(); result.unpack.return_value=('noctalia','vendor','5.4.1','1.2')
        bus=Mock(); bus.call_sync.return_value=result
        process=Mock(stdout='10\n')
        with patch('niri_feel.low_controls.Gio.bus_get_sync',return_value=bus), \
             patch('niri_feel.low_controls.shutil.which',return_value='/usr/bin/noctalia'), \
             patch('niri_feel.low_controls.subprocess.run',return_value=process):
            self.assertFalse(noctalia_owns(15))
            self.assertTrue(noctalia_owns(10))
            self.assertTrue(noctalia_owns(5))
            process.stdout='15\n'
            self.assertTrue(noctalia_owns(15))

class GlowTests(unittest.TestCase):
    def test_glow_stays_at_edges_and_finishes_without_a_fullscreen_tint(self):
        import gi
        gi.require_version('Gtk','4.0'); gi.require_version('Gdk','4.0')
        from niri_feel.low_visual import render_glow, GLOW_DURATION, PREVIEW_GLOW_DURATION
        for duration in (GLOW_DURATION,PREVIEW_GLOW_DURATION):
            for elapsed in (0,1,duration-.8,duration):
                surface=cairo.ImageSurface(cairo.FORMAT_ARGB32,640,360)
                render_glow(cairo.Context(surface),640,360,elapsed,duration)
                surface.flush()
                pixels=bytes(surface.get_data())
                self.assertEqual(any(pixels),0<elapsed<duration)
                offset=180*surface.get_stride()+320*4
                self.assertEqual(pixels[offset:offset+4],b'\x00'*4)
                self.assertLessEqual(max(pixels[3::4]),145)
                if elapsed==1:
                    # Visible haze, not the almost-invisible alpha of the old aura.
                    self.assertGreater(max(pixels[3::4]),70)

@unittest.skipUnless(os.environ.get("NIRI_FEEL_GUI_TEST")=="1", "Requires an opt-in live Niri session")
class PointerRegionTests(unittest.TestCase):
    def test_hidden_options_does_not_intercept_the_center_choice(self):
        import gi
        gi.require_version('Gtk','4.0'); gi.require_version('Gdk','4.0')
        from gi.repository import Gtk, Gdk, Gio, GLib
        from types import SimpleNamespace
        from niri_feel.low_visual import LowWindow, install_style
        Gtk.init()
        app=Gtk.Application(application_id=None,flags=Gio.ApplicationFlags.NON_UNIQUE)
        app.register(None)
        display=Gdk.Display.get_default()
        css=Gtk.CssProvider(); css.load_from_data(b"window { background: transparent; }")
        Gtk.StyleContext.add_provider_for_display(display,css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        install_style(display)
        window=LowWindow(app,display.get_monitors().get_item(0),
                         SimpleNamespace(preview=True,reveal=lambda:None),True)
        loop=GLib.MainLoop(); failures=[]
        window.arm_handle()
        def choices():
            window.show_card("","",[("Brightness",lambda:None)])
            return False
        def inspect():
            try:
                button=window.card.get_first_child().get_first_child()
                ok,bounds=button.compute_bounds(window)
                self.assertTrue(ok)
                x=bounds.get_x()+bounds.get_width()/2
                y=bounds.get_y()+bounds.get_height()/2
                target=window.pick(x,y,Gtk.PickFlags.DEFAULT)
                while target is not None and target is not button:
                    target=target.get_parent()
                self.assertIs(target,button,"Hidden Options overlay intercepted the center choice")
                rx,ry,rw,rh=window.input_bounds
                self.assertTrue(rx<=x<rx+rw and ry<=y<ry+rh)
            except Exception as error:
                failures.append(error)
            finally:
                loop.quit()
            return False
        GLib.timeout_add(450,choices)
        GLib.timeout_add(1150,inspect)
        try:
            loop.run()
        finally:
            window.stop()
        if failures:
            raise failures[0]

if __name__=='__main__':
    unittest.main()
