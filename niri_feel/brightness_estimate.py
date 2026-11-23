"""Conservative presentation estimates; absent sensor values stay unavailable."""
import math


def _valid_positive(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value > 0)


def discharge_watts(battery, online):
    """UPower's measured aggregate battery discharge rate, if applicable."""
    if (battery is None or online is not False or battery.state != 2
            or not _valid_positive(battery.watts)):
        return None
    return f"{battery.watts:.1f} W total battery discharge"


def estimate(battery, online):
    """Estimated remaining time while discharging; otherwise hide the value."""
    if battery is None or online is not False or battery.state != 2:
        return None
    seconds = battery.time_to_empty
    if online is False and isinstance(seconds, int) and not isinstance(seconds, bool) and seconds > 0:
        minutes = round(seconds / 60)
        return f"~{minutes // 60}h {minutes % 60:02d}m estimated"
    energy, rate = battery.energy, battery.watts
    if (not isinstance(energy, (int, float)) or isinstance(energy, bool)
            or not math.isfinite(energy) or energy < 0 or not _valid_positive(rate)):
        return None
    hours = energy / rate
    minutes = round(hours * 60)
    return f"~{minutes // 60}h {minutes % 60:02d}m estimated"
