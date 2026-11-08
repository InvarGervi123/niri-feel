"""UPower session edges, sparse checkpoints, and conservative sleep accounting."""
from dataclasses import replace
import sqlite3
from gi.repository import Gio, GLib
from .energy import Sensors
from .sessions import Sessions, SessionStore

class EnergyService:
    def __init__(self, changed=lambda: None, database=None):
        self.sensors = Sensors()
        self.sessions = Sessions(SessionStore(database))
        self.changed = changed
        self.fast = False
        self.timer = 0
        self.sleeping = False
        self.bus = None
        self.subscription = 0
        self.closed = False
        self.known_power = None
        self.last_completed = None
        self.recording_error = None
        self.sample()
        Gio.bus_get(Gio.BusType.SYSTEM, None, self.bus_ready)

    @property
    def ledger(self):
        return self.sessions.ledger

    def bus_ready(self, source, result):
        try:
            connection = Gio.bus_get_finish(result)
            if self.closed:
                return
            self.bus = connection
            self.subscription = self.bus.signal_subscribe("org.freedesktop.login1",
                "org.freedesktop.login1.Manager", "PrepareForSleep",
                "/org/freedesktop/login1", None, Gio.DBusSignalFlags.NONE, self.sleep_signal)
        except GLib.Error:
            pass  # clock gap detection remains active

    def power_changed(self, online):
        if self.known_power == online:
            return
        previous = self.known_power
        self.known_power = online
        if online is False:
            self.last_completed = None
        summary = self.sample()
        if previous is False and online is True:
            self.last_completed = summary

    def take_summary(self):
        summary, self.last_completed = self.last_completed, None
        return summary

    def sleep_signal(self, connection, sender, path, interface, signal, params):
        if params.unpack()[0]:
            self.sample()
            self.sleeping = True
            self.ledger.sleep_pending = True
            if self.timer:
                GLib.source_remove(self.timer)
            self.timer = GLib.timeout_add_seconds(60, self.resume_watchdog)
        else:
            self.sleeping = False
            self.sample()
            self.ledger.sleep_pending = False

    def resume_watchdog(self):
        self.timer = 0
        self.sleeping = False
        self.sample()
        self.ledger.sleep_pending = False
        return False

    def tick(self):
        self.timer = 0
        self.sample()
        return False

    def sample(self):
        if self.timer:
            GLib.source_remove(self.timer)
            self.timer = 0
        if self.closed or self.sleeping:
            return None
        summary = None
        if self.known_power is not None or self.sessions.data is not None:
            raw = self.sensors.read()
            sample = replace(raw, external=self.known_power,
                             discharging=self.known_power is False and bool(raw.battery_id))
            try:
                summary = self.sessions.feed(sample)
                self.recording_error = None
            except (OSError, sqlite3.Error) as error:
                self.recording_error = str(error)
                self.sessions.break_continuity()
                print(f"Battery session checkpoint failed: {error}", flush=True)
        self.changed()
        interval = 2 if self.fast else (15 if self.known_power is False else 60)
        self.timer = GLib.timeout_add_seconds(interval, self.tick)
        return summary

    def set_visible(self, visible):
        self.fast = visible
        self.sample()

    def close(self):
        if self.closed:
            return
        if not self.sleeping and self.known_power is False:
            self.sample()
        self.closed = True
        if self.timer:
            GLib.source_remove(self.timer)
            self.timer = 0
        if self.subscription:
            self.bus.signal_unsubscribe(self.subscription)
        self.sessions.close()
