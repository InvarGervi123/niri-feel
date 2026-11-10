"""Read-only NetworkManager D-Bus subscription; no connectivity check calls."""
from gi.repository import Gio, GLib
from .network_model import internet_state, NetworkEdges

NAME="org.freedesktop.NetworkManager"
PATH="/org/freedesktop/NetworkManager"

class NetworkSource:
    def __init__(self,event,unknown=lambda:None):
        self.event=event; self.unknown=unknown
        self.edges=NetworkEdges(); self.proxy=None; self.timer=0; self.generation=0; self.closed=False
        self.watch=Gio.bus_watch_name(Gio.BusType.SYSTEM,NAME,Gio.BusNameWatcherFlags.NONE,self.appeared,self.vanished)

    def appeared(self,connection,name,owner):
        self.generation+=1; generation=self.generation
        def ready(source,result):
            if self.closed or generation!=self.generation: return
            try:
                self.proxy=Gio.DBusProxy.new_finish(result)
                self.proxy.connect("g-properties-changed",lambda *_:self.schedule())
                self.schedule()
            except GLib.Error:
                self.vanished(connection,name)
        Gio.DBusProxy.new(connection,Gio.DBusProxyFlags.DO_NOT_AUTO_START,None,NAME,PATH,NAME,None,ready)

    def schedule(self):
        if self.closed: return
        if self.timer: GLib.source_remove(self.timer)
        self.timer=GLib.timeout_add(1200,self.evaluate)

    def evaluate(self):
        self.timer=0
        def get(name):
            value=self.proxy.get_cached_property(name) if self.proxy else None
            return value.unpack() if value is not None else None
        state=get("State")
        online=internet_state(state,get("Connectivity"))
        if online is None:
            if state in (None,0,10): self.edges.update(None)
            # Unknown Internet reachability breaks download correlation, but a
            # later measured loss should still follow the last known online state.
            self.unknown()
        else:
            edge=self.edges.update(online)
            if edge: self.event(edge)
        return False

    def vanished(self,connection,name):
        self.generation+=1; self.proxy=None
        if self.timer: GLib.source_remove(self.timer); self.timer=0
        self.edges.update(None); self.unknown()

    def close(self):
        self.closed=True; self.generation+=1
        Gio.bus_unwatch_name(self.watch)
        if self.timer: GLib.source_remove(self.timer); self.timer=0
        self.proxy=None
