import unittest
from niri_feel.power import Battery
from niri_feel.brightness_estimate import estimate, discharge_watts


class BrightnessEstimateTests(unittest.TestCase):
    def test_energy_rate_is_labeled_as_estimate(self):
        battery = Battery(state=2, watts=10, energy=25)
        self.assertEqual(estimate(battery, False), '~2h 30m estimated')
        self.assertEqual(discharge_watts(battery, False), '10.0 W total battery discharge')

    def test_unavailable_inputs_stay_unavailable(self):
        self.assertIsNone(estimate(None, False))
        self.assertIsNone(estimate(Battery(state=2, watts=0, energy=20), False))
        self.assertIsNone(estimate(Battery(state=1, watts=10, energy=20), True))
        self.assertIsNone(discharge_watts(Battery(state=1, watts=10), True))
        self.assertIsNone(discharge_watts(Battery(state=2, watts=float('nan')), False))
        self.assertIsNone(discharge_watts(Battery(state=4, watts=10), False))
        self.assertIsNone(estimate(Battery(state=4, energy=20, watts=10), False))

    def test_upower_time_to_empty_is_used_and_stays_labeled_estimate(self):
        self.assertEqual(estimate(Battery(state=2, time_to_empty=3720), False), '~1h 02m estimated')
        self.assertIsNone(estimate(Battery(state=2, time_to_empty=3720), True))


if __name__ == '__main__':
    unittest.main()
