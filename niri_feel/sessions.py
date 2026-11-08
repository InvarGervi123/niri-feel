"""Durable battery sessions. stdlib SQLite, bounded history, no UI dependencies."""
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import sqlite3
import time
from .energy import Ledger


def default_database():
    return Path(os.environ.get("XDG_STATE_HOME", Path.home()/".local/state"))/"niri-feel"/"sessions.sqlite3"


def boot_id():
    return Path("/proc/sys/kernel/random/boot_id").read_text().strip()


def sample_dict(sample):
    return asdict(sample)


class SessionStore:
    def __init__(self, path=None):
        self.path = None if path == ":memory:" else (Path(path) if path else default_database())
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(self.path or ":memory:", timeout=2)
        if self.path:
            self.path.chmod(0o600)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY, closed INTEGER NOT NULL, data TEXT NOT NULL);
            CREATE UNIQUE INDEX IF NOT EXISTS one_open_session ON sessions(closed) WHERE closed=0;
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY, session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                wall REAL NOT NULL, sample TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS readings_session ON readings(session_id);
        """)
        self.writes = 0

    def open_session(self):
        row = self.db.execute("SELECT id,data FROM sessions WHERE closed=0").fetchone()
        return (row[0],json.loads(row[1])) if row else (None,None)

    def save(self, identity, data, sample, wall, closed=False):
        payload = json.dumps(data, separators=(",",":"), allow_nan=False)
        reading = json.dumps(sample_dict(sample), separators=(",",":"), allow_nan=False)
        with self.db:
            if identity is None:
                identity = self.db.execute("INSERT INTO sessions(closed,data) VALUES(?,?)",(int(closed),payload)).lastrowid
            else:
                self.db.execute("UPDATE sessions SET closed=?,data=? WHERE id=?",(int(closed),payload,identity))
            self.db.execute("INSERT INTO readings(session_id,wall,sample) VALUES(?,?,?)",(identity,wall,reading))
            self.writes += 1
            if closed or self.writes % 128 == 0:
                self.db.execute("DELETE FROM readings WHERE id NOT IN (SELECT id FROM readings ORDER BY id DESC LIMIT 8192)")
                self.db.execute("DELETE FROM sessions WHERE closed=1 AND id NOT IN (SELECT id FROM sessions ORDER BY id DESC LIMIT 128)")
        return identity

    def close(self):
        self.db.close()


class Sessions:
    def __init__(self, store, current_boot=None):
        self.store = store
        self.boot = current_boot or boot_id()
        self.identity, self.data = store.open_session()
        self.ledger = Ledger()
        self.last_power = None
        self.continuous = False
        if self.data:
            for key,value in self.data["ledger"].items():
                if hasattr(self.ledger,key):
                    setattr(self.ledger,key,value)
            self.ledger.previous = None
            self.ledger.settle_until = 0
            self.data["interrupted"] = True
            self.ledger.gaps += 1

    def checkpoint(self, sample, wall, closed=False):
        self.data["ledger"] = self.ledger.summary()
        self.data["last"] = dict(sample=sample_dict(sample), wall=wall, boot_id=self.boot)
        self.identity = self.store.save(self.identity,self.data,sample,wall,closed)

    def begin(self, sample, wall):
        self.ledger = Ledger()
        self.identity = None
        self.data = dict(start=sample_dict(sample), start_wall=wall, start_boot=self.boot,
            start_observed=self.last_power is True, active_seconds=0., sleep_seconds=0.,
            unknown_seconds=0., unknown_duration=False, interrupted=False,
            battery_changed=False, end_observed=True, ledger={}, last=None)
        self.ledger.add(replace(sample,discharging=bool(sample.battery_id)))
        self.continuous = True
        self.checkpoint(sample,wall)

    def feed(self, sample, wall=None):
        wall = time.time() if wall is None else wall
        power = sample.external
        summary = None
        if self.data is None:
            if power is False:
                self.begin(sample,wall)
            self.last_power = power
            return None
        previous = self.data["last"]
        old = previous["sample"]
        same_boot = previous["boot_id"] == self.boot
        elapsed = max(0,sample.boot-old["boot"]) if same_boot else None
        active = max(0,sample.mono-old["mono"]) if same_boot else None
        if not same_boot:
            self.data["unknown_duration"] = True
        elif not self.continuous or power is None or (active > 90 and elapsed-active < .5):
            self.data["unknown_seconds"] += elapsed
        else:
            self.data["active_seconds"] += min(active,elapsed)
            self.data["sleep_seconds"] += max(0,elapsed-active)
        if json.loads(json.dumps(sample.battery_id)) != json.loads(json.dumps(self.data["start"]["battery_id"])):
            self.data["battery_changed"] = True
        if not self.continuous or power is None or not same_boot:
            self.ledger.previous = None
            self.ledger.live_cpu_w = None
        if power is None:
            self.ledger.gaps += int(self.last_power is not None)
            self.data["interrupted"] = True
            self.continuous = False
        else:
            # The reconnect sample closes the battery-side interval. Source state is
            # from UPower; net battery readings at event boundaries have gauge latency.
            self.ledger.add(replace(sample,external=False,discharging=bool(sample.battery_id)))
            self.continuous = True
        reconnect = power is True
        if reconnect:
            self.data["end_observed"] = self.last_power is False and previous["boot_id"] == self.boot
            summary = self.summary(sample)
            self.data["summary"] = summary
        self.checkpoint(sample,wall,closed=reconnect)
        if reconnect:
            self.identity, self.data = None,None
            self.continuous = False
        self.last_power = power
        return summary

    def summary(self, sample):
        data = self.data
        start = data["start"]
        endpoints = (not data["battery_changed"] and bool(start["battery_id"])
            and data["end_observed"])
        wh = start["wh"]-sample.wh if endpoints and start["wh"] is not None and sample.wh is not None else None
        pp = start["percent"]-sample.percent if endpoints and start["percent"] is not None and sample.percent is not None else None
        duration = max(0,sample.boot-start["boot"]) if (data["start_boot"]==self.boot and data["end_observed"]) else None
        notes = []
        if not data["start_observed"]:
            notes.append("Unplug time unobserved · measured since startup")
        if data["interrupted"]:
            notes.append("Recording gap · power changes during downtime unknown")
        if not data["end_observed"]:
            notes.append("Reconnect time unobserved · endpoint totals unavailable")
        if data["battery_changed"]:
            notes.append("Battery changed or unavailable · endpoint totals omitted")
        if self.ledger.gaps or self.ledger.counter_gaps:
            notes.append("Partial measurement coverage")
        if duration is not None and duration < 5:
            notes.insert(0,"Very short session · battery gauge may not resolve the change")
        measured_wh = self.ledger.awake_wh+self.ledger.sleep_wh if self.ledger.awake_intervals+self.ledger.sleep_intervals else None
        return dict(wh=wh, percentage_points=pp, duration=duration,
            measured_wh=measured_wh, cpu_wh=self.ledger.cpu_wh if self.ledger.cpu_seconds >= 1 else None,
            cpu_seconds=self.ledger.cpu_seconds, active_seconds=data["active_seconds"],
            sleep_seconds=data["sleep_seconds"], unknown_seconds=data["unknown_seconds"],
            unknown_duration=data["unknown_duration"], start_observed=data["start_observed"],
            end_observed=data["end_observed"], battery_gaps=self.ledger.gaps,
            cpu_gaps=self.ledger.counter_gaps, interrupted=data["interrupted"], notes=notes, preview=False)

    def break_continuity(self):
        self.continuous = False
        self.ledger.previous = None
        if self.data:
            self.data["interrupted"] = True

    def close(self):
        self.store.close()
