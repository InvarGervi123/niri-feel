"""Event-driven Linux backlight monitor, including writes from external tools."""
from pathlib import Path
from gi.repository import Gio, GLib


class BrightnessMonitor:
    def __init__(self, changed):
        self.changed = changed
        self.monitors = []
        self.timer = 0
        self.last = None
        self._install()

    def _install(self):
        for path in Path('/sys/class/backlight').glob('*'):
            try:
                file = Gio.File.new_for_path(str(path))
                monitor = file.monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES, None)
                monitor.connect('changed', self._event)
                self.monitors.append(monitor)
            except (OSError, GLib.Error):
                pass
        self.refresh(False)

    def _event(self, *_):
        if self.timer:
            GLib.source_remove(self.timer)
        self.timer = GLib.timeout_add(100, self._debounced)

    def _debounced(self):
        self.timer = 0
        self.refresh(True)
        return GLib.SOURCE_REMOVE

    def refresh(self, notify=True):
        readings = []
        for path in Path('/sys/class/backlight').glob('*'):
            try:
                value = int((path/'brightness').read_text())
                maximum = int((path/'max_brightness').read_text())
                if maximum > 0 and 0 <= value <= maximum:
                    readings.append(value / maximum * 100)
            except (OSError, ValueError):
                continue
        value = round(sum(readings) / len(readings)) if readings else None
        if value != self.last:
            self.last = value
            if notify:
                self.changed(value, len(readings))

    def close(self):
        if self.timer:
            GLib.source_remove(self.timer)
        for monitor in self.monitors:
            monitor.cancel()
