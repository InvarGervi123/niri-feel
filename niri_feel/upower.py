"""Read-only, asynchronous UPower adapter; no polling while idle."""
import time
from gi.repository import Gio, GLib
from .power import Battery, EdgeDetector

SERVICE = "org.freedesktop.UPower"
ROOT = "/org/freedesktop/UPower"
DEVICE = ROOT + "/devices/DisplayDevice"

class PowerSource:
    def __init__(self, changed, event):
        self.changed, self.event = changed, event
        self.root = self.device = None
        self.detector = EdgeDetector()
        self.online = None
        self.battery = None
        self.generation = 0
        self.watch = Gio.bus_watch_name(Gio.BusType.SYSTEM, SERVICE,
            Gio.BusNameWatcherFlags.NONE, self.appeared, self.vanished)

    def appeared(self, connection, name, owner):
        self.generation += 1
        generation = self.generation
        self.root = self.device = None
        self.detector.update(None)
        self.pending = 2
        for path, interface, attr in ((ROOT, SERVICE, "root"),
                (DEVICE, SERVICE + ".Device", "device")):
            def ready(source, result, attr=attr, generation=generation):
                if generation != self.generation:
                    return
                try:
                    proxy = Gio.DBusProxy.new_finish(result)
                    setattr(self, attr, proxy)
                    proxy.connect("g-properties-changed", self.properties_changed)
                except GLib.Error as error:
                    print(f"UPower unavailable: {error.message}", flush=True)
                self.pending -= 1
                if not self.pending:
                    self.refresh()
            Gio.DBusProxy.new(connection, Gio.DBusProxyFlags.DO_NOT_AUTO_START,
                None, SERVICE, path, interface, None, ready)

    def vanished(self, connection, name):
        self.generation += 1
        self.root = self.device = None
        self.online = self.battery = None
        self.detector.update(None)
        self.changed()

    def properties_changed(self, proxy, changed, invalidated):
        if not self.pending:
            self.refresh()

    @staticmethod
    def get(proxy, name, default=None):
        value = proxy.get_cached_property(name) if proxy else None
        return value.unpack() if value is not None else default

    def refresh(self):
        on_battery = self.get(self.root, "OnBattery")
        self.online = not on_battery if isinstance(on_battery, bool) else None
        if self.get(self.device, "IsPresent", False):
            self.battery = Battery(self.get(self.device, "State", 0),
                self.get(self.device, "Percentage"), self.get(self.device, "EnergyRate"),
                self.get(self.device, "UpdateTime", 0))
        else:
            self.battery = None
        edge = self.detector.update(self.online)
        self.changed()
        if edge:
            self.event(edge)

    def close(self):
        Gio.bus_unwatch_name(self.watch)
