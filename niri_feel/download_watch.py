"""Bounded, event-driven Downloads metadata observation. No content reads."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time
from gi.repository import Gio, GLib
from .network_model import DownloadEvidence,kind_for,inspect_partial,scan_partials

class DownloadWatch:
    def __init__(self,changed,directory=None):
        self.directory=Path(directory or GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD) or Path.home()/"Downloads").absolute()
        self.changed=changed; self.model=DownloadEvidence()
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix="niri-feel-downloads")
        self.pending=set(); self.timer=0; self.settle_timer=0; self.closed=False; self.generation=0
        self.monitor=None; self.available=False; self.jobs=0
        try:
            self.monitor=Gio.File.new_for_path(str(self.directory)).monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES,None)
            self.monitor.connect("changed",self.file_event)
            self.available=True
            self.work(lambda:scan_partials(self.directory),self.model.seed)
        except GLib.Error:
            print("Network Recovery: Downloads monitoring unavailable; network aura remains available.",flush=True)

    def work(self,operation,callback):
        if self.closed: return
        if self.jobs>=4:
            self.model.cancel(); self.changed([])
            return
        self.jobs+=1
        generation=self.generation
        future=self.pool.submit(operation)
        def done(future):
            try: result=future.result()
            except Exception: result=None
            def deliver():
                self.jobs-=1
                if not self.closed and generation==self.generation and result is not None:
                    callback(result)
                return False
            GLib.idle_add(deliver)
        future.add_done_callback(done)

    def file_event(self,monitor,file,other,event):
        if self.closed: return
        for value in (file,other):
            raw=value.get_path() if value else None
            if raw:
                path=Path(raw)
                if path.parent==self.directory:
                    # Payload changes must also refresh an adjacent aria2 sidecar.
                    if kind_for(path): self.pending.add(path)
                    else: self.pending.add(Path(str(path)+".aria2"))
        if len(self.pending)>256:
            self.pending.clear(); self.model.cancel()
            self.changed([])
        if not self.timer: self.timer=GLib.timeout_add(200,self.flush)

    def flush(self):
        self.timer=0
        paths=list(self.pending); self.pending.clear()
        def ready(items):
            before=set(self.model.visible)
            for path,item in items: self.model.observe(path,item,time.monotonic())
            if before!=set(self.model.visible): self.changed(self.model.items())
        self.work(lambda:[(path,inspect_partial(path)) for path in paths],ready)
        return False

    def disconnected(self):
        self.generation+=1
        if self.settle_timer: GLib.source_remove(self.settle_timer); self.settle_timer=0
        self.model.disconnected(time.monotonic())

    def reconnected(self,ready):
        if self.model.offline_at is None or not self.available:
            ready([]); return
        def baseline(items):
            self.model.reconnected(items)
            def settle():
                self.settle_timer=0
                self.work(lambda:scan_partials(self.directory),lambda items:ready(self.model.settled(items)))
                return False
            self.settle_timer=GLib.timeout_add(4000,settle)
        self.work(lambda:scan_partials(self.directory),baseline)

    def cancel(self):
        self.generation+=1; self.model.cancel()
        if self.settle_timer: GLib.source_remove(self.settle_timer); self.settle_timer=0
        self.changed([])

    def close(self):
        self.closed=True; self.generation+=1
        if self.monitor: self.monitor.cancel()
        for timer in (self.timer,self.settle_timer):
            if timer: GLib.source_remove(timer)
        self.pool.shutdown(wait=False,cancel_futures=True)
