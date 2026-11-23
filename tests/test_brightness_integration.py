import unittest

from niri_feel.brightness_visual import BrightnessOSD, update_power_windows
from niri_feel.power import EdgeDetector
from niri_feel.upower import PowerSource


class Variant:
    def __init__(self, value):
        self.value = value

    def unpack(self):
        return self.value


class Proxy:
    def __init__(self, values):
        self.values = values

    def get_cached_property(self, name):
        return Variant(self.values[name]) if name in self.values else None


class LabelProbe:
    def __init__(self):
        self.text = ''
        self.visible = False

    def set_text(self, value):
        self.text = value

    def set_visible(self, value):
        self.visible = value


class OSDProbe:
    # Exercise the actual BrightnessOSD update methods without creating a
    # compositor surface in the headless test runner.
    update_power = BrightnessOSD.update_power
    _refresh_secondary = BrightnessOSD._refresh_secondary

    def __init__(self):
        self.secondary = LabelProbe()
        self.power_text = LabelProbe()
        self.time_text = LabelProbe()
        self.online = self.battery = None


class BrightnessDataFlowTests(unittest.TestCase):
    def test_upower_refresh_reaches_visible_osd_secondary_row(self):
        app = OSDProbe()
        source = PowerSource.__new__(PowerSource)
        source.root = Proxy({'OnBattery': True})
        source.device = Proxy({
            'IsPresent': True,
            'State': 2,
            'Percentage': 62.0,
            'EnergyRate': 8.0,
            'Energy': 24.0,
            'TimeToEmpty': 0,
            'UpdateTime': 100,
        })
        source.detector = EdgeDetector()
        source.pending = 0
        source.online = source.battery = None
        source.event = lambda _edge: None
        source.changed = lambda: update_power_windows(
            (app,), source.online, source.battery)

        source.refresh()

        self.assertFalse(source.online)
        self.assertEqual(source.battery.watts, 8.0)
        self.assertTrue(app.secondary.visible)
        self.assertEqual(app.secondary.text,
                         '')
        self.assertEqual(app.power_text.text, '8.0 W total battery discharge')
        self.assertEqual(app.time_text.text, '~3h 00m estimated')
        self.assertTrue(app.power_text.visible)
        self.assertTrue(app.time_text.visible)

        # UPower property signals run the same refresh callback while the OSD is
        # active, so the row changes without another brightness event.
        source.device.values['EnergyRate'] = 6.0
        source.device.values['Energy'] = 18.0
        source.device.values['TimeToEmpty'] = 10_800
        source.properties_changed(source.device, {'EnergyRate': Variant(6.0)}, [])
        self.assertEqual(app.power_text.text, '6.0 W total battery discharge')
        self.assertEqual(app.time_text.text, '~3h 00m estimated')

    def test_charging_or_full_state_hides_both_values(self):
        app = OSDProbe()
        app.update_power(False, type('Battery', (), {
            'state': 2, 'watts': 5.0, 'energy': 20.0, 'time_to_empty': 0,
        })())
        self.assertTrue(app.secondary.visible)
        app.update_power(True, type('Battery', (), {
            'state': 1, 'watts': 12.0, 'energy': 20.0, 'time_to_empty': 0,
        })())
        self.assertFalse(app.secondary.visible)
        self.assertFalse(app.power_text.visible)
        self.assertFalse(app.time_text.visible)


if __name__ == '__main__':
    unittest.main()
