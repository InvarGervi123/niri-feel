import argparse
import signal
import sqlite3
import sys
import time


def main():
    parser=argparse.ArgumentParser(description="Niri Feel — power arrives, your battery story returns")
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument("--preview",choices=("connect","disconnect","both"),help="preview original charger animations")
    modes.add_argument("--preview-session",action="store_true",help="preview unplug, collection, reconnect and summary; simulated, isolated data")
    modes.add_argument("--status",action="store_true",help="print live UPower status and exit")
    args=parser.parse_args()
    from gi.repository import Gio, GLib
    from .power import describe
    from .upower import PowerSource
    if args.status:
        loop=GLib.MainLoop()
        result=[1]
        def status():
            if source.root is None or source.device is None:
                return
            title,detail=describe(source.online,source.battery,time.time())
            print(title+(" · "+detail if detail else ""))
            result[0]=0
            loop.quit()
        def timeout():
            print("UPower unavailable",file=sys.stderr)
            loop.quit()
            return False
        source=PowerSource(status,lambda _:None)
        GLib.timeout_add_seconds(5,timeout)
        loop.run(); source.close()
        return result[0]
    try:
        from .visual import EdgeLight,Layer,Gtk,Gdk
        from .session_visual import SUMMARY_DURATION
    except (ValueError,ImportError) as error:
        print(f"Missing graphical dependency: {error}\nInstall gtk4-layer-shell; see README.md.",file=sys.stderr)
        return 1
    preview=bool(args.preview or args.preview_session)

    class Feel(Gtk.Application):
        def __init__(self):
            super().__init__(application_id=None if preview else "org.nirifeel.Charging",
                flags=Gio.ApplicationFlags.NON_UNIQUE if preview else Gio.ApplicationFlags.DEFAULT_FLAGS)
            self.windows_by_monitor={}
            self.source=None
            self.energy=None
            self.preview_model=None
            self.timers=set()
            self.sequence=[]

        def later(self,milliseconds,callback):
            def fire():
                self.timers.discard(timer)
                callback()
                return False
            timer=GLib.timeout_add(milliseconds,fire)
            self.timers.add(timer)

        def do_activate(self):
            if self.source or self.windows_by_monitor:
                print("Niri Feel is already listening.",flush=True)
                return
            if not Layer.is_supported():
                print("Wayland layer-shell is not available.",file=sys.stderr)
                self.quit(); return
            css=Gtk.CssProvider()
            css.load_from_data(b"window { background: transparent; box-shadow: none; }")
            Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(),css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            self.hold()
            self.monitors=Gdk.Display.get_default().get_monitors()
            self.monitors.connect("items-changed",lambda *_:self.sync_monitors())
            self.sync_monitors()
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT,signal.SIGINT,self.exit_signal)
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT,signal.SIGTERM,self.exit_signal)
            if args.preview_session:
                from .session_preview import PreviewSession
                self.preview_model=PreviewSession()
                self.later(500,self.preview_unplug)
            elif args.preview:
                self.source=PowerSource(self.update_text,lambda _:None)
                self.sequence=["connect","disconnect"] if args.preview=="both" else [args.preview]
                self.later(650,self.next_preview)
            else:
                from .energy_service import EnergyService
                try:
                    self.energy=EnergyService()
                    print(f"Session history: {self.energy.sessions.store.path}",flush=True)
                except (OSError,sqlite3.Error) as error:
                    print(f"Session recording unavailable: {error}",file=sys.stderr)
                self.source=PowerSource(self.update_text,self.power_event)
                print("Listening · unplug to start a session · reconnect for your summary. Ctrl+C to stop.",flush=True)

        def exit_signal(self):
            self.quit()
            return False

        def sync_monitors(self):
            current={self.monitors.get_item(i) for i in range(self.monitors.get_n_items())}
            for monitor in set(self.windows_by_monitor)-current:
                self.windows_by_monitor.pop(monitor).stop()
            for monitor in current-set(self.windows_by_monitor):
                self.windows_by_monitor[monitor]=EdgeLight(self,monitor)

        def update_text(self):
            if not self.source:
                return
            if self.energy:
                self.energy.power_changed(self.source.online)
            title,detail=describe(self.source.online,self.source.battery,time.time())
            for window in self.windows_by_monitor.values():
                if args.preview:
                    window.detail="Preview · "+title+(" · "+detail if detail else "")
                else:
                    window.title_text,window.detail=title,detail

        def power_event(self,kind):
            summary=self.energy.take_summary() if kind=="connect" and self.energy else None
            self.play(kind,summary=summary)

        def play(self,kind,summary=None,title=None,detail=None):
            if title is None:
                title,detail=describe(self.source.online,self.source.battery,time.time())
                if args.preview:
                    detail="Preview · "+title+(" · "+detail if detail else "")
                    title="Power connected" if kind=="connect" else "Power disconnected"
            for window in self.windows_by_monitor.values():
                window.play(kind,title,detail or "",summary)
            print(f"{kind}: {title}"+(" · session summary" if summary else ""),flush=True)

        def next_preview(self):
            if not self.sequence:
                self.quit(); return
            self.play(self.sequence.pop(0))
            self.later(4100,self.next_preview)

        def preview_unplug(self):
            self.preview_model.unplug()
            self.play("disconnect",title="Preview · Battery session started",
                      detail="Collecting simulated readings · real history stays untouched")
            self.later(1600,self.preview_collect)
            self.later(4100,self.preview_reconnect)

        def preview_collect(self):
            self.preview_model.collect()
            print("Preview: collected 45 virtual minutes, including sleep, in memory only.",flush=True)

        def preview_reconnect(self):
            summary=self.preview_model.reconnect()
            self.play("connect",summary=summary,title="Preview · Back on power",detail="Simulated session")
            self.later(round((SUMMARY_DURATION+.4)*1000),self.quit)

        def do_shutdown(self):
            for timer in self.timers:
                GLib.source_remove(timer)
            if self.energy:
                self.energy.close()
            if self.source:
                self.source.close()
            if self.preview_model:
                self.preview_model.close()
            for window in list(self.windows_by_monitor.values()):
                window.stop()
            Gtk.Application.do_shutdown(self)

    return Feel().run([sys.argv[0]])

if __name__=="__main__":
    raise SystemExit(main())
