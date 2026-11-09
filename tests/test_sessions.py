import json
from pathlib import Path
import tempfile
import unittest
import cairo
from niri_feel.energy import Counter, Sample
from niri_feel.sessions import Sessions, SessionStore
from niri_feel.session_preview import PreviewSession
from niri_feel.session_visual import render_summary, SUMMARY_DURATION, SUMMARY_HEIGHT


def reading(t,online=False,wh=30,pp=80,boot=None,energy=None,identity=(("BAT0",1,"battery"),),counters=True):
    return Sample(t,t if boot is None else boot,identity,wh,pp,not online,
        {"intel-rapl:0":Counter(int(100_000_000+t*3.6e6 if energy is None else energy),262_143_328_850,("package",1))} if counters else {},online)

class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/"sessions.sqlite3"
        self.store=SessionStore(self.path)
        self.sessions=Sessions(self.store,"boot-a")

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def begin(self):
        self.sessions.feed(reading(0,True),0)
        self.sessions.feed(reading(1),1)

    def test_automatic_end_with_endpoint_and_cpu_measurements(self):
        self.begin()
        self.sessions.feed(reading(16,wh=29.95,pp=79),16)
        result=self.sessions.feed(reading(31,True,29.9,78),31)
        self.assertAlmostEqual(result['wh'],.1)
        self.assertEqual(result['percentage_points'],2)
        self.assertEqual(result['duration'],30)
        self.assertAlmostEqual(result['cpu_wh'],.03)
        self.assertEqual(result['active_seconds'],30)
        self.assertTrue(result['start_observed'])
        self.assertTrue(result['end_observed'])
        self.assertIsNone(self.store.open_session()[0])
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM readings').fetchone()[0],3)

    def test_restart_continues_session_but_does_not_bridge_cpu(self):
        self.begin()
        self.sessions.feed(reading(16,wh=29.95),16)
        self.store.close()
        self.store=SessionStore(self.path)
        self.sessions=Sessions(self.store,"boot-a")
        self.sessions.feed(reading(61,wh=29.8),61)
        result=self.sessions.feed(reading(76,True,29.75,79),76)
        self.assertAlmostEqual(result['wh'],.25)
        self.assertEqual(result['duration'],75)
        self.assertEqual(result['unknown_seconds'],45)
        self.assertEqual(result['active_seconds'],30)
        self.assertEqual(result['cpu_seconds'],30)
        self.assertAlmostEqual(result['cpu_wh'],.03)
        self.assertTrue(any('Recording gap' in note for note in result['notes']))

    def test_restart_already_plugged_does_not_invent_endpoints(self):
        self.begin(); self.sessions.feed(reading(16,wh=29.95),16)
        self.store.close(); self.store=SessionStore(self.path)
        self.sessions=Sessions(self.store,'boot-a')
        result=self.sessions.feed(reading(100,True,35,90),100)
        self.assertIsNone(result['wh'])
        self.assertIsNone(result['percentage_points'])
        self.assertIsNone(result['duration'])
        self.assertAlmostEqual(result['measured_wh'],.05)
        self.assertFalse(result['end_observed'])

    def test_reboot_does_not_use_old_clock_or_rapl_baseline(self):
        self.begin(); self.sessions.feed(reading(16,wh=29.95),16)
        self.store.close(); self.store=SessionStore(self.path)
        self.sessions=Sessions(self.store,'boot-b')
        self.sessions.feed(reading(2,wh=29.7),100)
        result=self.sessions.feed(reading(17,True,29.6,79),115)
        self.assertIsNone(result['duration'])
        self.assertTrue(result['unknown_duration'])
        self.assertEqual(result['cpu_seconds'],30)
        self.assertTrue(any('Recording gap' in note for note in result['notes']))

    def test_rapid_changes_are_separate_sessions_no_duplicate_close(self):
        self.begin()
        first=self.sessions.feed(reading(1.2,True),1.2)
        self.assertAlmostEqual(first['duration'],.2)
        self.assertIsNone(self.sessions.feed(reading(1.3,True),1.3))
        self.sessions.feed(reading(1.4),1.4)
        second=self.sessions.feed(reading(1.6,True),1.6)
        self.assertAlmostEqual(second['duration'],.2)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM sessions WHERE closed=1').fetchone()[0],2)

    def test_missing_energy_is_not_a_zero(self):
        self.sessions.feed(reading(0,True),0)
        self.sessions.feed(reading(1,wh=None,pp=None,counters=False),1)
        result=self.sessions.feed(reading(16,True,wh=None,pp=None,counters=False),16)
        self.assertIsNone(result['wh']); self.assertIsNone(result['percentage_points'])
        self.assertIsNone(result['cpu_wh']); self.assertIsNone(result['measured_wh'])
        self.assertEqual(result['duration'],15)

    def test_sleep_time_separate_and_cpu_excluded(self):
        self.begin()
        self.sessions.feed(reading(16,wh=29.95),16)
        self.sessions.feed(reading(17,wh=29.9,boot=317),317)
        result=self.sessions.feed(reading(32,True,29.85,79,boot=332),332)
        self.assertEqual(result['duration'],331)
        self.assertEqual(result['sleep_seconds'],300)
        self.assertEqual(result['active_seconds'],31)
        self.assertEqual(result['cpu_seconds'],15)
        self.assertAlmostEqual(result['cpu_wh'],.015)

    def test_missing_power_is_a_gap_not_a_reconnect(self):
        self.begin()
        self.sessions.feed(reading(16,online=None,wh=29.95),16)
        self.assertIsNotNone(self.sessions.data)
        self.sessions.feed(reading(31,wh=29.9),31)
        result=self.sessions.feed(reading(46,True,29.85,79),46)
        self.assertEqual(result['unknown_seconds'],30)
        self.assertEqual(result['cpu_seconds'],15)

    def test_changed_battery_does_not_create_endpoint_totals(self):
        self.begin()
        other=(("BAT0",2,"replacement"),)
        self.sessions.feed(reading(16,wh=40,identity=other),16)
        result=self.sessions.feed(reading(31,True,39,90,identity=other),31)
        self.assertIsNone(result['wh']); self.assertIsNone(result['percentage_points'])

    def test_start_on_battery_is_an_observed_partial_session(self):
        self.sessions.feed(reading(1),1)
        result=self.sessions.feed(reading(16,True,29.95,79),16)
        self.assertFalse(result['start_observed'])
        self.assertEqual(result['duration'],15)

    def test_database_permissions_and_atomic_saved_snapshot(self):
        self.begin(); self.sessions.feed(reading(16,wh=29.95),16)
        self.assertEqual(self.path.stat().st_mode & 0o777,0o600)
        identity,data=self.store.open_session()
        self.assertIsNotNone(identity)
        self.assertEqual(data['last']['sample']['wh'],29.95)
        self.assertAlmostEqual(data['ledger']['cpu_wh'],.015)
        self.assertEqual(self.store.db.execute('PRAGMA integrity_check').fetchone()[0],'ok')

    def test_history_is_bounded(self):
        for index in range(140):
            t=index*3
            self.sessions.feed(reading(t,True),t)
            self.sessions.feed(reading(t+1),t+1)
            self.sessions.feed(reading(t+2,True),t+2)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM sessions').fetchone()[0],128)

class PreviewTests(unittest.TestCase):
    def test_full_sequence_is_simulated_and_does_not_open_a_real_database(self):
        preview=PreviewSession()
        try:
            self.assertIsNone(preview.store.path)
            preview.unplug(); preview.collect(); result=preview.reconnect()
            self.assertTrue(result['preview'])
            self.assertAlmostEqual(result['wh'],4.06)
            self.assertEqual(result['sleep_seconds'],900)
            self.assertGreater(result['cpu_wh'],0)
            self.assertEqual(preview.store.db.execute('SELECT count(*) FROM sessions WHERE closed=1').fetchone()[0],1)
        finally:
            preview.close()

    def test_summary_fades_and_can_render_missing_values(self):
        for summary in ({'preview':True},{'wh':.3,'percentage_points':1,'duration':180,'cpu_wh':.1,'cpu_seconds':100}):
            for t in (0,.2,.4,1,3.8,4.3,SUMMARY_DURATION):
                surface=cairo.ImageSurface(cairo.FORMAT_ARGB32,1920,SUMMARY_HEIGHT)
                render_summary(cairo.Context(surface),1920,SUMMARY_HEIGHT,t,summary)
                surface.flush()
                self.assertEqual(any(surface.get_data()),.25<t<SUMMARY_DURATION)

class ServiceTests(unittest.TestCase):
    def test_upower_edges_finalize_once_and_prepare_automatic_summary(self):
        from unittest.mock import patch
        from niri_feel.energy_service import EnergyService
        with tempfile.TemporaryDirectory() as directory, patch('niri_feel.energy_service.Gio.bus_get'):
            service=EnergyService(database=Path(directory)/'test.sqlite3')
            try:
                with patch.object(service.sensors,'read',return_value=reading(0,True)):
                    service.power_changed(True)
                self.assertIsNone(service.take_summary())
                with patch.object(service.sensors,'read',return_value=reading(1)):
                    service.power_changed(False)
                with patch.object(service.sensors,'read',return_value=reading(16,wh=29.95)):
                    service.sample()
                with patch.object(service.sensors,'read',return_value=reading(31,True,29.9,79)):
                    service.power_changed(True)
                result=service.take_summary()
                self.assertAlmostEqual(result['wh'],.1)
                self.assertAlmostEqual(result['cpu_wh'],.03)
                self.assertIsNone(service.take_summary())
                service.power_changed(True)
                self.assertIsNone(service.take_summary())
            finally:
                service.close()

    def test_startup_reconnect_archive_is_not_an_observed_event(self):
        from unittest.mock import patch
        from niri_feel.energy_service import EnergyService
        from niri_feel.sessions import boot_id
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'test.sqlite3'
            store=SessionStore(path); sessions=Sessions(store,boot_id())
            sessions.feed(reading(0,True),0); sessions.feed(reading(1),1); store.close()
            with patch('niri_feel.energy_service.Gio.bus_get'):
                service=EnergyService(database=path)
            try:
                with patch.object(service.sensors,'read',return_value=reading(100,True,35,90)):
                    service.power_changed(True)
                self.assertIsNone(service.take_summary())
                self.assertIsNone(service.sessions.data)
            finally:
                service.close()

if __name__=='__main__':
    unittest.main()
