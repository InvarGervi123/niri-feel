"""Conservative presentation estimates; absent sensor values stay unavailable."""
import math


def estimate(battery, online):
    # UPower Energy and EnergyRate are gauge-reported Wh and W. The quotient is
    # an estimate, and is only useful while discharging or charging.
    if battery is None or online is None:
        return "Unavailable"
    seconds = battery.time_to_empty
    if online is False and isinstance(seconds, int) and not isinstance(seconds, bool) and seconds > 0:
        minutes = round(seconds / 60)
        return f"~{minutes // 60}h {minutes % 60:02d}m estimated"
    energy, rate = battery.energy, battery.watts
    if not all(isinstance(x, (int, float)) and not isinstance(x, bool)
               and math.isfinite(x) for x in (energy, rate)) or rate <= 0 or energy < 0:
        return "Unavailable"
    hours = energy / rate if online is False else None
    if online is True:
        # UPower's EnergyFull is not currently part of the shared Battery model.
        return "Unavailable"
    if hours is None:
        return "Unavailable"
    minutes = round(hours * 60)
    return f"~{minutes // 60}h {minutes % 60:02d}m estimated"


def display_power():
    # Linux backlight interfaces expose level, not panel electrical power.
    return "Unavailable"
