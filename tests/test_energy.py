import tempfile
import unittest
from pathlib import Path
from niri_feel.energy import Counter, Sample, Sensors, Ledger, counter_delta, UJ_PER_WH


def sample(t, wh=30, percent=80, value=100_000_000, discharge=True,
           boot=None, identity=("BAT0",), counters=True):
    return Sample(t, t if boot is None else boot, identity, wh, percent,
        discharge, {"intel-rapl:0": Counter(value, 262_143_328_850, ("package",1))} if counters else {},
        not discharge)

class LedgerTests(unittest.TestCase):
    def test_energy_conversion_and_separate_readings(self):
        l=Ledger()
        l.add(sample(0))
        l.add(sample(15,29.9,79,154_000_000))
        self.assertAlmostEqual(l.awake_wh,.1)
        self.assertEqual(l.awake_pp,1)
        self.assertAlmostEqual(l.cpu_wh,.015)
        self.assertAlmostEqual(l.live_cpu_w,3.6)
        self.assertEqual(l.cpu_seconds,15)

    def test_sleep_is_not_cpu_energy(self):
        l=Ledger()
        l.add(sample(0))
        l.add(sample(15,29.9,79,154_000_000))
        l.add(sample(16,29.8,78,200_000_000,boot=1816))
        self.assertAlmostEqual(l.sleep_wh,.1)
        self.assertAlmostEqual(l.awake_wh,.1)
        self.assertAlmostEqual(l.cpu_wh,.015)
        self.assertIsNone(l.live_cpu_w)
        self.assertEqual(l.sleep_seconds,1801)
        l.add(sample(18,29.79,78,207_200_000,boot=1818))
        self.assertEqual(l.cpu_seconds,15)
        l.add(sample(50,29.78,78,310_000_000,boot=1850))
        self.assertEqual(l.cpu_seconds,15)
        l.add(sample(52,29.77,78,317_200_000,boot=1852))
        self.assertEqual(l.cpu_seconds,17)

    def test_cpu_can_be_measured_without_battery_wh(self):
        l=Ledger(); l.add(sample(0,wh=None)); l.add(sample(15,wh=None,value=154_000_000))
        self.assertEqual(l.awake_intervals,0)
        self.assertAlmostEqual(l.cpu_wh,.015)
        self.assertEqual(l.cpu_seconds,15)

    def test_signal_marks_short_sleep(self):
        l=Ledger(); l.add(sample(0)); l.sleep_pending=True
        l.add(sample(1,29.99,value=101_000_000))
        self.assertEqual(l.sleep_intervals,1)
        self.assertEqual(l.cpu_seconds,0)

    def test_plugged_and_transition_intervals_are_excluded(self):
        l=Ledger()
        l.add(sample(0,discharge=False))
        l.add(sample(2,discharge=False,value=107_200_000))
        self.assertAlmostEqual(l.live_cpu_w,3.6)
        self.assertEqual(l.cpu_wh,0)
        l.add(sample(4,29.9,value=114_400_000))
        self.assertEqual(l.awake_wh,0)
        self.assertEqual(l.cpu_wh,0)
        self.assertEqual(l.gaps,1)

    def test_missing_battery_identity_and_long_gaps(self):
        for end in (sample(15,wh=None),sample(15,identity=("other",)),sample(200,29)):
            l=Ledger(); l.add(sample(0)); l.add(end)
            self.assertEqual(l.awake_wh,0)
            self.assertEqual(l.gaps,1)

    def test_missing_rapl_does_not_become_zero_measurement(self):
        l=Ledger(); l.add(sample(0)); l.add(sample(15,29.9,counters=False))
        self.assertAlmostEqual(l.awake_wh,.1)
        self.assertEqual(l.cpu_seconds,0)
        self.assertEqual(l.counter_gaps,1)
        self.assertIsNone(l.live_cpu_w)

    def test_gauge_increase_offsets_loss(self):
        l=Ledger(); l.add(sample(0)); l.add(sample(15,29.9)); l.add(sample(30,29.95))
        self.assertAlmostEqual(l.awake_wh,.05)

class CounterTests(unittest.TestCase):
    def test_wrap_near_boundary(self):
        a=Counter(99_000_000,100_000_000,(1,))
        b=Counter(1_000_000,100_000_000,(1,))
        self.assertAlmostEqual(counter_delta(a,b,.05),2_000_000/UJ_PER_WH)

    def test_reset_range_change_identity_spike_and_ambiguous_wrap(self):
        a=Counter(50_000_000,100_000_000,(1,))
        for b,dt in ((Counter(0,100_000_000,(1,)),.05),
                     (Counter(51_000_000,110_000_000,(1,)),.05),
                     (Counter(51_000_000,100_000_000,(2,)),.05),
                     (Counter(99_000_000,100_000_000,(1,)),.001),
                     (Counter(51_000_000,100_000_000,(1,)),100)):
            self.assertIsNone(counter_delta(a,b,dt))

class DiscoveryTests(unittest.TestCase):
    def test_overlapping_domains_never_selected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name,label in (("intel-rapl:0","package-0"),("intel-rapl:0:0","core"),
                               ("intel-rapl:0:1","uncore"),("intel-rapl-mmio:0","package-0")):
                p=root/name; p.mkdir(); (p/"name").write_text(label)
            s=Sensors(root/"missing", root)
            self.assertEqual([p.name for p in s.domains],["intel-rapl:0"])

    def test_micro_wh_conversion_and_missing_battery(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); bat=root/"BAT0"; bat.mkdir()
            for name,value in {"type":"Battery","present":"1","status":"Discharging",
                               "energy_now":"30123000","energy_full":"39599000","capacity":"76"}.items():
                (bat/name).write_text(value)
            s=Sensors(root,root/"none"); reading=s.read()
            self.assertEqual(reading.wh,30.123)
            self.assertEqual(reading.percent,76)
            self.assertTrue(reading.discharging)
            (bat/"energy_now").write_text("invalid")
            self.assertIsNone(s.read().wh)

if __name__ == "__main__":
    unittest.main()
