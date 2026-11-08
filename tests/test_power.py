import unittest
from niri_feel.power import Battery, EdgeDetector, describe

class PowerTests(unittest.TestCase):
    def test_no_startup_or_duplicate_animation(self):
        d = EdgeDetector()
        self.assertIsNone(d.update(True))
        self.assertIsNone(d.update(True))
        self.assertEqual(d.update(False), "disconnect")
        self.assertEqual(d.update(True), "connect")

    def test_missing_data_is_not_an_unplug(self):
        d = EdgeDetector()
        for value in (True, None, False):
            self.assertIsNone(d.update(value))

    def test_full_is_not_zero_watt_charging(self):
        self.assertEqual(describe(True, Battery(4, 100, 0, 1000), 1001),
                         ("Fully charged", "100%"))

    def test_only_fresh_charging_rate_is_presented(self):
        self.assertEqual(describe(True, Battery(1, 52, 18.25, 1000), 1001),
                         ("Charging", "52% · 18.2 W into battery"))
        self.assertEqual(describe(True, Battery(1, 52, 18.25, 1000), 1201),
                         ("Charging", ""))
        self.assertEqual(describe(False, Battery(2, 52, 12, 1000), 1001),
                         ("On battery", "52%"))

    def test_invalid_and_future_values_are_not_numbers(self):
        for watts in (float("nan"), float("inf"), -8, 0, None):
            self.assertEqual(describe(True, Battery(1, None, watts, 1000), 1001)[1], "")
        self.assertEqual(describe(True, Battery(1, 52, 18, 1100), 1001)[1], "")

if __name__ == "__main__":
    unittest.main()
