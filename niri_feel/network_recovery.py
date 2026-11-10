"""Local network recovery presentation. No resume, probes or telemetry."""
from pathlib import Path
from gi.repository import Gtk, Gdk, Gio, GLib
from .network_model import Partial, RecoveryItem, recovery_tip
from .network_visual import NetworkWindow, install_style


def preview_items():
    return [RecoveryItem(Partial(Path('/Preview/Downloads/example-image.iso.crdownload'),
        Path('/Preview/Downloads/example-image.iso.crdownload'),"chromium",("preview",1),
        ("preview",1),32*1024*1024,24*1024*1024),"Possibly affected · simulated, app status unknown")]


class NetworkRecovery:
    def __init__(self,app,preview=False,finished=lambda:None):
        self.app=app; self.preview=preview; self.finished=finished
        self.source=None; self.downloads=None
        self.windows=[]; self.timers=set(); self.expiry=0; self.generation=0; self.closed=False
        self.items=[]; self.index=0
        install_style(Gdk.Display.get_default())
        if not preview:
            from .download_watch import DownloadWatch
            from .network_source import NetworkSource
            self.downloads=DownloadWatch(self.files_changed)
            self.source=NetworkSource(self.event,self.unknown)

    def later(self,ms,callback):
        def fire():
            self.timers.discard(timer)
            if not self.closed: callback()
            return False
        timer=GLib.timeout_add(ms,fire); self.timers.add(timer)
        return timer

    def expire(self,ms):
        if self.expiry in self.timers:
            GLib.source_remove(self.expiry); self.timers.discard(self.expiry)
        self.expiry=self.later(ms,self.dismiss)

    def clear(self):
        self.generation+=1
        for timer in self.timers: GLib.source_remove(timer)
        self.timers.clear(); self.expiry=0
        for window in self.windows: window.stop()
        self.windows=[]; self.items=[]; self.index=0

    def aura(self,kind):
        monitors=Gdk.Display.get_default().get_monitors()
        self.windows=[NetworkWindow(self.app,monitors.get_item(i),self,kind)
                      for i in range(monitors.get_n_items())]

    def event(self,kind):
        self.clear()
        generation=self.generation
        self.aura(kind)
        if kind=="offline":
            self.downloads.disconnected()
            self.expire(3700)
        else:
            self.expire(8000)
            def ready(items):
                if generation==self.generation and not self.closed:
                    self.recovered(items)
            self.downloads.reconnected(ready)

    def recovered(self,items):
        if not items: return
        self.items=list(items); self.index=0
        self.present()

    def present(self,extend=True):
        if not self.items or not self.windows: return
        self.index%=len(self.items)
        target=next((w for w in self.windows if (w.network_monitor.get_connector() or '').startswith('eDP')),self.windows[0])
        item=self.items[self.index]
        target.show_item(item,self.index,len(self.items),recovery_tip(item.partial.kind))
        if extend: self.expire(14000)

    def next_item(self):
        self.index+=1; self.present()

    def files_changed(self,items):
        if not self.items: return
        self.items=list(items)
        if not self.items: self.dismiss()
        else: self.present(extend=False)

    def open_folder(self):
        if self.preview:
            for window in self.windows:
                if hasattr(window,'note'): window.note.set_text("Preview only · no folder opened.")
            return
        directory=self.downloads.directory
        if not directory.is_dir():
            for window in self.windows:
                if hasattr(window,'note'): window.note.set_text("Folder is no longer available.")
            return
        def opened(source,result):
            try:
                Gio.AppInfo.launch_default_for_uri_finish(result)
                self.dismiss()
            except GLib.Error:
                for window in self.windows:
                    if hasattr(window,'note'): window.note.set_text("The file manager could not be opened.")
        Gio.AppInfo.launch_default_for_uri_async(directory.as_uri(),None,None,opened)

    def dismiss(self):
        if self.expiry in self.timers:
            GLib.source_remove(self.expiry); self.timers.discard(self.expiry)
        self.expiry=0
        for window in self.windows: window.fade_help()
        def finish():
            self.clear()
            if self.preview: self.finished()
        self.later(550,finish)

    def unknown(self):
        self.clear()
        if self.downloads: self.downloads.cancel()

    def start_preview(self):
        print("Preview · simulated network loss and partial download. No real files or network settings are accessed.",flush=True)
        self.aura('offline')
        def returned():
            self.clear(); self.aura('online')
            self.later(3600,lambda:self.recovered(preview_items()))
        self.later(4200,returned)

    def close(self):
        self.closed=True; self.clear()
        if self.source: self.source.close()
        if self.downloads: self.downloads.close()
