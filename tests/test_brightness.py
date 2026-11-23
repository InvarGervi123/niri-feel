import unittest
from niri_feel.power import Battery
from niri_feel.brightness_estimate import estimate, display_power


class BrightnessEstimateTests(unittest.TestCase):
    def test_energy_rate_is_labeled_as_estimate(self):
        self.assertEqual(estimate(Battery(watts=10, energy=25), False), '~2h 30m estimated')

    def test_unavailable_inputs_stay_unavailable(self):
        self.assertEqual(estimate(None, False), 'Unavailable')
        self.assertEqual(estimate(Battery(watts=0, energy=20), False), 'Unavailable')
        self.assertEqual(estimate(Battery(watts=10, energy=20), True), 'Unavailable')
        self.assertEqual(display_power(), 'Unavailable')

    def test_upower_time_to_empty_is_used_and_stays_labeled_estimate(self):
        self.assertEqual(estimate(Battery(time_to_empty=3720), False), '~1h 02m estimated')
        self.assertEqual(estimate(Battery(time_to_empty=3720), True), 'Unavailable')


if __name__ == '__main__':
    unittest.main()
