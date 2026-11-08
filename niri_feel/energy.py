"""Bounded-memory energy accounting. No GTK, policy writes or inferred components."""
from dataclasses import dataclass, field
from pathlib import Path
import math
import re
import time

UJ_PER_WH = 3_600_000_000

@dataclass(frozen=True)
class Counter:
    value: int
    maximum: int
    identity: tuple

@dataclass(frozen=True)
class Sample:
    mono: float
    boot: float
    battery_id: tuple = ()
    wh: float | None = None
    percent: float | None = None
    discharging: bool = False
    counters: dict = field(default_factory=dict)
    external: bool | None = None


def number(path):
    try:
        value = float(path.read_text().strip())
        return value if math.isfinite(value) and value >= 0 else None
    except (OSError, ValueError):
        return None


class Sensors:
    def __init__(self, supply="/sys/class/power_supply", powercap="/sys/class/powercap"):
        self.supply, self.powercap = Path(supply), Path(powercap)
        self.domains = []
        self.discover()

    def discover(self):
        self.domains = []
        # Select one transport, top-level package zones only. Never sum children.
        for path in sorted(self.powercap.glob("intel-rapl:*")):
            if not re.fullmatch(r"intel-rapl:\d+", path.name):
                continue
            try:
                if re.fullmatch(r"package-\d+", (path/"name").read_text().strip()):
                    self.domains.append(path)
            except OSError:
                pass

    def read(self):
        batteries, adapters = [], []
        for path in sorted(self.supply.glob("*")):
            try:
                kind = (path/"type").read_text().strip()
                if kind == "Battery" and number(path/"present") != 0:
                    batteries.append(path)
                elif (path/"online").exists():
                    adapters.append(number(path/"online"))
            except OSError:
                pass
        external = any(v == 1 for v in adapters) if adapters and all(v is not None for v in adapters) else None
        whs, percents, fulls, states, ids = [], [], [], [], []
        for path in batteries:
            try:
                ids.append((str(path.resolve()), path.stat().st_ino,
                            (path/"serial_number").read_text().strip() if (path/"serial_number").exists() else ""))
                states.append((path/"status").read_text().strip())
                whs.append(number(path/"energy_now"))
                percents.append(number(path/"capacity"))
                fulls.append(number(path/"energy_full"))
            except OSError:
                states.append("Unknown")
        energy = sum(whs)/1e6 if whs and len(whs)==len(batteries) and all(v is not None for v in whs) else None
        percent = None
        if len(percents)==1:
            percent = percents[0]
        elif percents and all(v is not None for v in percents+fulls) and sum(fulls)>0:
            percent = sum(a*b for a,b in zip(percents,fulls))/sum(fulls)
        if percent is not None and not 0 <= percent <= 100:
            percent = None
        counters = {}
        for path in self.domains:
            try:
                value, maximum = number(path/"energy_uj"), number(path/"max_energy_range_uj")
                if value is not None and maximum and value <= maximum:
                    counters[path.name] = Counter(int(value), int(maximum),
                        (str(path.resolve()), (path/"energy_uj").stat().st_ino))
            except OSError:
                pass
        return Sample(time.monotonic(), time.clock_gettime(time.CLOCK_BOOTTIME),
            tuple(ids), energy, percent,
            bool(states) and len(states)==len(batteries) and all(s=="Discharging" for s in states) and external is not True,
            counters, external)


def counter_delta(old, new, seconds):
    if seconds <= 0 or old.identity != new.identity or old.maximum != new.maximum:
        return None
    delta = new.value - old.value
    if delta < 0:
        # Accept only a wrap very near the boundary. Other decreases are resets.
        if old.value < old.maximum*.9 or new.value > new.maximum*.1:
            return None
        delta += old.maximum
    # Reject spikes and ambiguous intervals that could contain multiple wraps.
    if seconds*1000*1e6 >= old.maximum or delta > seconds*1000*1e6:
        return None
    return delta/UJ_PER_WH


class Ledger:
    def __init__(self):
        self.previous = None
        self.awake_wh = self.awake_pp = self.sleep_wh = self.sleep_pp = 0.0
        self.awake_seconds = self.sleep_seconds = self.cpu_seconds = 0.0
        self.cpu_wh = 0.0
        self.awake_intervals = self.sleep_intervals = self.pp_intervals = self.sleep_pp_intervals = 0
        self.gaps = self.counter_gaps = 0
        self.live_cpu_w = None
        self.sleep_pending = False
        self.settle_until = 0.0
        self.last_interval = "Waiting for a second reading"

    def add(self, sample):
        old, self.previous = self.previous, sample
        self.live_cpu_w = None
        if old is None:
            return
        dt = sample.mono-old.mono
        elapsed = sample.boot-old.boot
        if dt <= 0 or elapsed <= 0:
            self.gaps += 1
            return
        crossed_sleep = self.sleep_pending or elapsed-dt > .5
        if crossed_sleep:
            self.settle_until = sample.boot+30
        sleeping = crossed_sleep or old.boot < self.settle_until
        # Delayed callbacks are also not an awake attribution window.
        uncertain = dt > 90 and not sleeping
        matching = old.battery_id and old.battery_id == sample.battery_id
        battery_interval = (matching and old.discharging and sample.discharging
            and old.wh is not None and sample.wh is not None and not uncertain)
        if battery_interval:
            decrease = old.wh-sample.wh
            # Signed deltas preserve gauge corrections instead of inventing loss.
            if sleeping:
                self.sleep_wh += decrease
                self.sleep_seconds += elapsed
                self.sleep_intervals += 1
            else:
                self.awake_wh += decrease
                self.awake_seconds += dt
                self.awake_intervals += 1
            if old.percent is not None and sample.percent is not None:
                if sleeping:
                    self.sleep_pp += old.percent-sample.percent
                    self.sleep_pp_intervals += 1
                else:
                    self.awake_pp += old.percent-sample.percent
                    self.pp_intervals += 1
        elif old.discharging or sample.discharging:
            self.gaps += 1
        if sleeping:
            self.last_interval = "Sleep / resume window · CPU attribution paused"
            return
        if uncertain:
            self.last_interval = "Sampling gap · interval excluded"
            return
        deltas = []
        for key in old.counters.keys() & sample.counters.keys():
            delta = counter_delta(old.counters[key], sample.counters[key], dt)
            if delta is not None:
                deltas.append(delta)
        complete = bool(sample.counters) and old.counters.keys()==sample.counters.keys() and len(deltas)==len(sample.counters)
        if complete:
            self.live_cpu_w = sum(deltas)*3600/dt
            if matching and old.discharging and sample.discharging:
                self.cpu_wh += sum(deltas)
                self.cpu_seconds += dt
        elif old.discharging and sample.discharging:
            self.counter_gaps += 1
        self.last_interval = "Measuring on battery" if sample.discharging else "External power · battery accounting paused"

    def summary(self):
        return {key: value for key,value in vars(self).items()
                if key not in ("previous", "sleep_pending")}
