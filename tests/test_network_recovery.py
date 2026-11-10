import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from dataclasses import replace
from niri_feel.network_model import (internet_state,NetworkEdges,Partial,DownloadEvidence,
    inspect_partial,scan_partials,recovery_tip)


def partial(name="demo.crdownload",length=4096,allocated=4096,version=1,identity=(1,2,None),kind="chromium"):
    path=Path('/Preview/Downloads')/name
    return Partial(path,path,kind,identity,(identity,length,allocated,version),length,allocated)

class ConnectivityTests(unittest.TestCase):
    def test_connected_link_is_not_internet_evidence(self):
        self.assertIsNone(internet_state(70,0))
        self.assertIsNone(internet_state(0,4))
        self.assertIsNone(internet_state(10,1))
        self.assertTrue(internet_state(70,4))
        self.assertFalse(internet_state(20,4))
        self.assertFalse(internet_state(50,3))
        self.assertFalse(internet_state(70,2))

    def test_seed_duplicate_and_daemon_restart_do_not_invent_an_outage(self):
        edges=NetworkEdges()
        self.assertIsNone(edges.update(True))
        self.assertIsNone(edges.update(True))
        self.assertEqual(edges.update(False),'offline')
        self.assertIsNone(edges.update(False))
        self.assertEqual(edges.update(True),'online')
        self.assertIsNone(edges.update(None))
        self.assertIsNone(edges.update(True))

class NetworkSourceTests(unittest.TestCase):
    def test_transient_unknown_measurement_does_not_hide_a_later_known_loss(self):
        from gi.repository import GLib
        from niri_feel.network_source import NetworkSource
        from unittest.mock import Mock
        source=NetworkSource.__new__(NetworkSource)
        source.edges=NetworkEdges(); source.event=Mock(); source.unknown=Mock()
        props={"State":70,"Connectivity":4}
        source.proxy=Mock()
        source.proxy.get_cached_property.side_effect=lambda name:GLib.Variant('u',props[name])
        source.evaluate()
        props['Connectivity']=0; source.evaluate()
        source.unknown.assert_called_once()
        props.update(State=20,Connectivity=1); source.evaluate()
        source.event.assert_called_once_with('offline')

class EvidenceTests(unittest.TestCase):
    def prepare(self):
        model=DownloadEvidence(); old=partial()
        model.seed([old]); new=partial(length=8192,allocated=8192,version=2)
        model.observe(new.marker,new,90); model.disconnected(100)
        return model,new

    def test_old_partial_is_not_blame_for_the_disconnect(self):
        model=DownloadEvidence(); item=partial()
        model.seed([item]); model.disconnected(100); model.reconnected([item])
        self.assertEqual(model.settled([item]),[])

    def test_recent_observed_change_and_stall_is_only_possible_evidence(self):
        model,item=self.prepare(); model.reconnected([item])
        result=model.settled([item])
        self.assertEqual(len(result),1)
        self.assertIn('Possibly affected',result[0].status)
        self.assertIn('unknown',result[0].status)

    def test_stale_activity_is_excluded(self):
        model,item=self.prepare(); model.disconnected(200); model.reconnected([item])
        self.assertEqual(model.settled([item]),[])

    def test_recent_creation_during_disconnect_grace_can_be_considered(self):
        model=DownloadEvidence(); model.disconnected(100)
        item=partial(); model.observe(item.marker,item,105); model.reconnected([item])
        self.assertEqual(len(model.settled([item])),1)
        model=DownloadEvidence(); model.disconnected(100)
        model.observe(item.marker,item,120); model.reconnected([item])
        self.assertEqual(model.settled([item]),[])

    def test_growing_or_rewritten_after_reconnect_is_not_reported(self):
        for change in (partial(length=12288,version=3),partial(length=8192,allocated=8192,version=3)):
            model,item=self.prepare(); model.reconnected([item])
            self.assertEqual(model.settled([change]),[])

    def test_completed_removed_and_replaced_files_are_excluded(self):
        model,item=self.prepare(); model.reconnected([item])
        self.assertEqual(model.settled([]),[])
        model,item=self.prepare(); model.reconnected([item])
        self.assertEqual(model.settled([replace(item,identity=(1,9,None))]),[])

    def test_later_activity_removes_visible_help(self):
        model,item=self.prepare(); model.reconnected([item]); model.settled([item])
        model.observe(item.marker,partial(length=16384,version=5),130)
        self.assertEqual(model.items(),[])

    def test_unknown_connection_clears_pending_evidence(self):
        model,item=self.prepare(); model.cancel(); model.reconnected([item])
        self.assertEqual(model.settled([item]),[])

    def test_metadata_and_sidecar_of_one_payload_are_not_double_counted(self):
        model=DownloadEvidence(); item=partial('file.part',kind='part')
        side=replace(partial('file.part.aria2',kind='aria2'),payload=item.payload)
        model.seed([item,side])
        for p in (item,side): model.observe(p.marker,replace(p,signature=(2,)),90)
        model.disconnected(100)
        candidates=list(model.entries.values()); model.reconnected(candidates)
        result=model.settled(candidates)
        self.assertEqual(len(result),1); self.assertEqual(result[0].partial.kind,'aria2')

class MetadataTests(unittest.TestCase):
    def test_no_contents_are_read_and_aria2_reports_payload_not_control_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); payload=root/'image.iso'; control=root/'image.iso.aria2'
            payload.write_bytes(b'x'*8192); control.write_bytes(b'control')
            with patch.object(Path,'read_bytes',side_effect=AssertionError('content read')), \
                 patch.object(Path,'read_text',side_effect=AssertionError('content read')):
                item=inspect_partial(control)
                self.assertEqual(item.length,8192)
                self.assertEqual(item.allocated,payload.stat().st_blocks*512)
                self.assertNotEqual(item.length,control.stat().st_size)
                self.assertEqual(len(scan_partials(root)),1)

    def test_missing_aria2_payload_has_unknown_data_size(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'missing.bin.aria2'; path.write_bytes(b'control')
            item=inspect_partial(path)
            self.assertIsNone(item.payload); self.assertIsNone(item.length)
            self.assertIsNone(item.allocated)

    def test_symlink_partial_and_symlink_payload_are_never_followed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); actual=root/'real'; actual.write_bytes(b'x')
            link=root/'danger.part'; link.symlink_to(actual)
            self.assertIsNone(inspect_partial(link))
            control=root/'link.aria2'; control.write_bytes(b'x'); (root/'link').symlink_to(actual)
            self.assertIsNone(inspect_partial(control).payload)

    def test_sparse_length_is_not_claimed_as_downloaded_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'sparse.crdownload'
            with path.open('wb') as f: f.truncate(4*1024*1024)
            item=inspect_partial(path)
            self.assertEqual(item.length,4*1024*1024)
            self.assertLess(item.allocated,item.length)

    def test_scan_is_top_level_only(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'nested').mkdir(); (root/'nested'/'hidden.part').touch()
            self.assertEqual(scan_partials(root),[])

    def test_tips_never_promise_recovery(self):
        self.assertIn('not known',recovery_tip('chromium'))
        self.assertIn('does not prove',recovery_tip('part'))
        self.assertIn('not known',recovery_tip('aria2'))

class NetworkPreviewTests(unittest.TestCase):
    def test_preview_data_is_labelled_and_does_not_touch_real_downloads(self):
        from niri_feel.network_recovery import preview_items
        with patch('niri_feel.network_model.os.stat',side_effect=AssertionError('Real metadata read')):
            items=preview_items()
        self.assertEqual(len(items),1)
        self.assertIn('simulated',items[0].status)
        self.assertNotEqual(items[0].partial.length,items[0].partial.allocated)

class RecoveryPresentationTests(unittest.TestCase):
    def test_no_candidates_means_no_generic_recovery_panel(self):
        from niri_feel.network_recovery import NetworkRecovery
        from unittest.mock import Mock
        controller=NetworkRecovery.__new__(NetworkRecovery)
        controller.present=Mock()
        controller.recovered([])
        controller.present.assert_not_called()

    def test_open_folder_uses_a_local_directory_uri_only_after_the_action(self):
        from niri_feel.network_recovery import NetworkRecovery
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            controller=NetworkRecovery.__new__(NetworkRecovery)
            controller.preview=False; controller.windows=[]
            controller.downloads=SimpleNamespace(directory=Path(directory))
            with patch('niri_feel.network_recovery.Gio.AppInfo.launch_default_for_uri_async') as launch:
                controller.open_folder()
                self.assertEqual(launch.call_count,1)
                self.assertEqual(launch.call_args.args[0],Path(directory).as_uri())

    def test_preview_open_folder_never_launches_a_real_application(self):
        from niri_feel.network_recovery import NetworkRecovery
        controller=NetworkRecovery.__new__(NetworkRecovery)
        controller.preview=True; controller.windows=[]
        with patch('niri_feel.network_recovery.Gio.AppInfo.launch_default_for_uri_async') as launch:
            controller.open_folder()
            launch.assert_not_called()

class FileMonitorTests(unittest.TestCase):
    def test_real_directory_events_correlate_and_later_growth_removes_help(self):
        from gi.repository import GLib
        from niri_feel.download_watch import DownloadWatch
        import time
        def wait_for(predicate,seconds=6):
            loop=GLib.MainLoop(); deadline=time.monotonic()+seconds; passed=[]
            def check():
                if predicate(): passed.append(True); loop.quit(); return False
                if time.monotonic()>deadline: loop.quit(); return False
                return True
            timer=GLib.timeout_add(25,check)
            loop.run()
            self.assertTrue(passed,'Timed out waiting for real file-monitor events')
        with tempfile.TemporaryDirectory() as directory:
            updates=[]; watch=DownloadWatch(lambda items:updates.append(items),directory)
            try:
                self.assertTrue(watch.available)
                wait_for(lambda:watch.jobs==0)
                path=Path(directory)/'test-download.crdownload'; path.write_bytes(b'fake-test-payload')
                wait_for(lambda:path in watch.model.activity)
                watch.disconnected()
                recovered=[]; watch.reconnected(lambda items:recovered.extend(items))
                wait_for(lambda:bool(recovered))
                self.assertEqual(recovered[0].partial.length,len(b'fake-test-payload'))
                path.write_bytes(b'fake-test-payload-that-grew')
                wait_for(lambda:bool(updates) and updates[-1]==[])
            finally:
                watch.close()

if __name__=='__main__': unittest.main()
