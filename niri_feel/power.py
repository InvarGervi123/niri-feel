"""Pure battery presentation logic. All quantities come from UPower."""
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class Battery:
    state: int = 0
    percentage: float | None = None
    watts: float | None = None
    updated: int = 0


def valid_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def describe(online: bool | None, battery: Battery | None, now: float):
    if online is False:
        title = "On battery"
    elif online is None:
        title = "Power status unavailable"
    elif battery and battery.state == 4:
        title = "Fully charged"
    elif battery and battery.state == 1:
        title = "Charging"
    else:
        title = "Power connected"
    details = []
    fresh = battery is not None and 0 <= now - battery.updated <= 120
    if fresh and valid_number(battery.percentage) and 0 <= battery.percentage <= 100:
        details.append(f"{battery.percentage:.0f}%")
    if (fresh and online is True and battery.state == 1
            and valid_number(battery.watts) and battery.watts > 0):
        details.append(f"{battery.watts:.1f} W into battery")
    return title, " · ".join(details)


class EdgeDetector:
    """Seed quietly; discard continuity across missing data / daemon restarts."""
    def __init__(self):
        self.previous = None

    def update(self, online):
        previous, self.previous = self.previous, online
        if previous is None or online is None or previous == online:
            return None
        return "connect" if online else "disconnect"
