# Niri Feel

<img width="800" height="450" alt="Niri Feel — Battery Session Demo" src="https://github.com/user-attachments/assets/921e902c-2455-4c60-b8e4-d9d5920b1217" />
<div align="center">

**A quieter way for your laptop to talk about energy.**

Charging light, battery sessions, and honest energy stories for Niri on Linux.

[Alpha](#alpha-status) · [Get started](#get-started) · [Preview](#try-the-experience) · [Measurement limits](#what-can-actually-be-measured) · [MIT](LICENSE)

</div>

---

Niri Feel turns everyday power events into small moments of light. Unplug your
laptop and carry on working. When power returns, a brief visual story shows what
your battery session measured, then fades back into your workspace.

The goal is an original, calm desktop experience: subtle motion, useful context,
and room to keep working. No dashboard to watch, chatbot, or power-policy engine.
All interface text is in English.

## Alpha status

**This is an early Alpha, not a stable release.** The current implementation has
been exercised on Niri with CachyOS and an Intel laptop. Hardware support and
measurement precision vary. Automated tests cover accounting and failure cases;
physical suspend and unplug/replug testing is still important on each machine.

The reconnect summary currently stays visible for approximately eight seconds.
Its size and timing are intentionally unchanged in this publication and may be
refined later. There are no stable release artifacts or packaged installers yet.

## What works today

- **Charging experience.** Two soft streams of light gather along the bottom edge
  when power connects; disconnecting releases the light and lets it fade.
- **Battery sessions.** Disconnecting starts a recording session. Reconnecting
  automatically shows a summary inside the same edge surface as the charging
  animation, with no competing notification window.
- **An honest session summary.** Net battery decrease in Wh and percentage points,
  elapsed session time, observed active/sleep/uncovered time, and independently
  measured Intel CPU-package energy with its own coverage duration.
- **Persistent local history.** Small SQLite checkpoints preserve readings and
  sessions across process restarts. Unobserved time is marked as a coverage gap.
- **Full-sequence preview.** Try disconnect → recording → reconnect → summary →
  fade without touching the charger or writing simulated data to real history.
- **Quiet integration.** The overlay does not take keyboard focus, capture pointer
  input, reserve screen space, or change Niri, Noctalia, or power profiles.

Low-battery effects and a welcome-back interface are not implemented in this Alpha.

## System requirements

| Component | Requirement |
| --- | --- |
| Desktop | Linux with Niri in a Wayland session; `gtk4-layer-shell` support |
| Runtime | Python 3.10 or newer; tested with Python 3.14 |
| Graphics | GTK4, PyGObject, Pycairo, and the Gtk4LayerShell introspection typelib |
| Power events | UPower over the system D-Bus |
| Sleep accounting | Linux monotonic/boottime clocks; logind signals when available |
| Battery energy | Readable `/sys/class/power_supply` battery energy/capacity fields |
| CPU energy | Readable Intel RAPL package counters under `/sys/class/powercap` |
| Storage | Python's built-in SQLite module; a writable user state directory |

Missing energy sensors do not become invented measurements. CPU values are omitted
when reliable RAPL coverage is unavailable. Other compositors and distributions
have not been validated by this project.

## Get started

### 1. Install runtime dependencies

On Arch Linux / CachyOS:

```sh
sudo pacman -S --needed python python-gobject python-cairo gtk4 gtk4-layer-shell upower
```

Other distributions need the equivalent packages, including GObject introspection
support for GTK4 and Gtk4LayerShell. There are no pip dependencies, AI services,
or additional database servers.

### 2. Clone the project

```sh
git clone https://github.com/InvarGervi123/niri-feel.git
cd niri-feel
```

### 3. Run inside your Niri session

```sh
./run
```

Leave the process running. Disconnect the charger to begin a session; reconnect
it to see the automatic summary. Nothing needs to be opened manually. The summary
fades away while recording remains ready for the next session.

Press **Ctrl+C** in the original terminal to stop. Committed history remains on
disk. A second normal invocation activates the existing process rather than
creating another collector.

The launcher loads the layer-shell library before GTK initializes its Wayland
backend. Use `./run` for the graphical experience.

## Try the experience

### Complete battery-session preview

```sh
./run --preview-session
```

The sequence lasts approximately 13 seconds. It compresses 45 virtual minutes,
including 15 minutes of sleep, into a short demonstration. The display is clearly
labelled **SIMULATED**. Its SQLite database exists only in memory: it does not
listen for real charger events, modify live accounting, or write synthetic data
to your history. The process exits when the summary has faded.

### Original charging animations

```sh
./run --preview connect
./run --preview disconnect
./run --preview both
```

These simulate the event and label it as a preview. Any battery values shown in
these original animation previews still come from live UPower readings.

### Read the current power status

```sh
python3 -m niri_feel --status
```

## What can actually be measured?

**Battery energy and CPU-package energy are separate observations, not a complete
component-by-component breakdown of the laptop.**

| Reading | Source | Meaning |
| --- | --- | --- |
| Battery decrease, Wh | Battery `energy_now` endpoints | Net change in energy reported by the battery gauge |
| Percentage-point decrease | Battery `capacity` endpoints | Change in the reported percentage, not a relative percentage calculation |
| CPU-package energy, Wh | Top-level Intel RAPL counters | Package energy over accepted, observed awake intervals |
| Active / sleep time | Monotonic and boottime clock differences | Observed time classification; missing recording intervals remain uncovered |
| Screen, SSD, RAM | No supported independent energy input | Not attributed separately |

Niri Feel reads power-source transitions from UPower and battery/RAPL energy
counters from sysfs. Battery micro-Wh are converted to Wh; RAPL microjoules are
divided by 3,600,000,000 to obtain Wh.

Only top-level `intel-rapl` package zones contribute CPU energy. Nested `core` and
`uncore` domains overlap the package, and the MMIO transport can expose a duplicate
package counter: neither is added again. Other component sensor types are not yet
supported and require verification before attribution can be added.

**Battery energy minus CPU energy is not a measurement of the other components.**
No such remainder is assigned to the display, SSD, RAM, or anything else. The
colored line in the summary represents **time**, not an energy-percentage chart.

### Coverage and precision

- CPU coverage excludes sleep-crossing intervals and a conservative 30-second
  resume-settling period. Battery loss near sleep cannot be attributed to CPU or
  other unmeasured components. logind signals are best effort; clock-gap detection
  and a resume watchdog provide fallback handling.
- Counter identity/range changes, ordinary resets, implausible spikes, missing
  samples, and ambiguous wraps break coverage. A reset indistinguishable from a
  plausible genuine increment cannot be detected by sysfs alone.
- Starting while already on battery produces an explicitly partial session from
  the first observed reading. The original unplug time cannot be reconstructed.
- Restarting on battery continues the stored session with an uncovered interval;
  CPU consumption is never extrapolated across that downtime. Unobserved power
  changes may have happened, so an interrupted duration is labelled a session span.
- Restarting already plugged in archives the previous open session without
  inventing its reconnect time or replaying it as a newly observed event.
- Reboots invalidate cross-boot elapsed-time assumptions. Only known time portions
  are reported. Battery replacement or missing endpoints omit endpoint totals.
- Gauge resolution, gauge corrections, and hardware/event update delays limit
  precision. A tiny session can have no resolved battery change; a correction can
  yield a negative net decrease. A delayed reconnect event can include some charging.
- Rapid transitions create separate, possibly very short sessions and replace the
  current visual effect instead of queuing competing notifications.

## Local data and resource use

Session data is stored at:

```text
${XDG_STATE_HOME:-~/.local/state}/niri-feel/sessions.sqlite3
```

The default database is user-local, mode `0600`, and never sent to a server by
Niri Feel. It can contain hardware identifiers from sysfs and usage timestamps:
keep it private. Database files, sidecars, local logs, and generated preview
screenshots are excluded from Git by [`.gitignore`](.gitignore).

Recording uses bounded in-memory aggregates and sparse SQLite transactions:

- One checkpoint about every **15 seconds on battery**, plus power/sleep boundaries.
- Idle sampling about once per minute on external power; no battery-session writes
  while connected without an open session.
- Up to **128 session records** and approximately **8,192 recent raw readings**,
  pruned periodically and at session end. Older retained sessions keep aggregates.
- Animation frame callbacks stop after the effect disappears.

A crash can lose readings since the last committed checkpoint, normally up to
15 seconds. A storage failure is reported in the terminal and breaks continuity
rather than claiming missing intervals were measured.

## Optional autostart

Autostart is **not installed or enabled** by this project. For now, run `./run`
from a terminal for the part of the day you want recorded.

If you choose to enable it later, one option is a Niri configuration entry using
the **absolute path to your own checkout**:

```kdl
spawn-at-startup "/absolute/path/to/niri-feel/run"
```

This is an example, not a configuration change performed by the application.
See [Niri's startup configuration documentation](https://niri-wm.github.io/niri/Configuration%3A-Miscellaneous.html#spawn-at-startup).
Niri Feel does not modify Noctalia settings or existing power-management tools.

## Development and testing

From the repository root, with the system dependencies installed:

```sh
python3 -m unittest discover -s tests -v
```

Tests cover energy conversions, overlapping counters, wraps/resets, missing data,
sleep separation, process restarts, reboots, rapid transitions, SQLite permissions
and retention, UPower edge wiring, preview isolation, and rendering/fade behavior.
They do not suspend the laptop or change its power configuration.

For a manual check, run the full preview while typing in another application;
then test a real unplug/replug cycle with the normal listener. Battery hardware
may take longer than one sampling interval to report a visible change.

Implementation: Python, GTK4/Cairo, GIO/D-Bus, gtk4-layer-shell, and standard-library
SQLite. The source and tests are intentionally small; there is no bundler or web UI.

Bug reports and contributions are welcome. Include your distribution, Niri/GTK
versions, and which counters are available. Do not attach private session databases
or unreviewed logs. Proposed attribution for a new component must explain the
sensor's meaning, units, and overlap with existing measurements.

## License

[MIT License](LICENSE) — Copyright © 2026 Niri Feel contributors.
