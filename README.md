# Niri Feel

<img width="800" height="450" alt="Niri Feel — Battery Session Demo" src="https://github.com/user-attachments/assets/921e902c-2455-4c60-b8e4-d9d5920b1217" />
<div align="center">

**A quieter way for your laptop to talk about energy.**

Charging light, battery sessions, and local network recovery for Niri on Linux.

[Alpha](#alpha-status) · [Get started](#get-started) · [Preview](#try-the-experience) · [Measurement limits](#what-can-actually-be-measured) · [Apache 2.0](LICENSE)

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

The compact reconnect summary stays visible for approximately 4.8 seconds.
Battery decrease, energy loss, and measured CPU energy take priority in its layout. There are no stable release artifacts or packaged installers yet.

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
- **Low Battery Experience.** A soft red aura at 15%, followed by visible Options
  for Performance or Brightness. Every system change requires separate confirmation.
- **Network Recovery.** Amber/green edge auras follow NetworkManager's reported
  loss and return of connectivity. Recently active partial downloads can receive
  a small, local recovery hint after reconnection; nothing resumes automatically.
- **Quiet integration.** Overlays do not steal keyboard focus or reserve screen
  space. Only visible controls receive pointer input. Niri and Noctalia settings
  are never rewritten; supported power changes happen only after confirmation.

A welcome-back interface is not implemented in this Alpha.

## System requirements

| Component | Requirement |
| --- | --- |
| Desktop | Linux with Niri in a Wayland session; `gtk4-layer-shell` support |
| Runtime | Python 3.10 or newer; tested with Python 3.14 |
| Graphics | GTK4, PyGObject, Pycairo, and the Gtk4LayerShell introspection typelib |
| Power events | UPower over the system D-Bus |
| Network recovery | An already-running NetworkManager; reported Connectivity results |
| Partial-download hints | An existing local XDG Downloads directory and GIO file-monitor support |
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

All previews run independently of real low-battery or connectivity events.

| Experience | Command |
| --- | --- |
| Charging light | `./run --preview both` |
| Battery Session Summary | `./run --preview-session` |
| Low Battery options and confirmation | `./run --preview-low-battery` |
| Network Recovery and partial-download hint | `./run --preview-network-recovery` |

### Complete battery-session preview

```sh
./run --preview-session
```

The sequence lasts approximately 10 seconds. It compresses 45 virtual minutes,
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

## Low Battery Experience

At a fresh on-battery reading of **15% or lower**, Niri Feel shows a soft rose-red
edge aura for 3.2 seconds (6 seconds in Preview). Broad, graduated haze drifts along
the edges; the center of the screen stays untouched. This first layer has no words, buttons,
panel, or pointer input region. It fades completely.

As the aura begins to fade, a small semi-transparent **Options** button appears
at the bottom center. Its label is always visible; no hover discovery is needed.
Clicking reveals a compact, floating action strip:
**Performance**, **Brightness**, **Dismiss**. Nothing functional opens without
that intent. Choosing a priority shows its explanation and a **separate Apply
change button** before any real system request. There is no framed popup card.

Low Battery and Network Recovery share floating mint typography, lightweight
vector action icons, and a soft, unframed shade behind the text. Their spacing
and fades follow the Battery Session Summary; labelled controls remain clickable
without taking keyboard focus. The edge auras are unchanged.

| Priority | Proposed change | Kept unchanged |
| --- | --- | --- |
| Performance | Dim the supported internal display to 80% of its current level | Current CPU power profile |
| Brightness | Switch the existing power-profiles-daemon to `power-saver` | Screen brightness |

For example, Performance proposes 100% → 80% brightness, or 50% → 40%.
It does not enable a faster CPU profile. Brightness may reduce CPU performance.
Unsupported options explain why they cannot be applied. Existing profile holds
from other applications are respected. If the profile, brightness or other checked
capabilities change after review, confirmation is rejected and must be reviewed
again. Changes are one-shot requests; no background enforcement, automatic restore,
new power service, governor write or privileged fallback is installed.

Brightness uses the existing logind `SetBrightness` interface, only when one
readable internal backlight is available. Power profiles use the already-running
power-profiles-daemon. The application does not auto-start these services. An OS
permission failure is reported; it does not trigger a sudo fallback.

If ignored, Options softly fades after about eight seconds. The Preview stays
running without applying any changes. The intent-revealed strip has a 10-second idle timeout; review has a 30-second timeout.
Timeout, Cancel and Dismiss never apply settings. Keyboard focus stays in your
working application. Only Options, then the explicitly revealed controls,
accept pointer input; the rest of the edge surface remains click-through.
Connecting power cancels the low-battery UI before the existing charging experience plays.

The alert is latched across process restarts in a small user-local
`low-battery.json` beside the session database. It re-arms only after a fresh
reading at or above 20%, so charger flapping and threshold jitter do not repeat
alerts. Session SQLite data is not changed by this feature.

### Noctalia coexistence

Niri Feel does not send a duplicate desktop notification, stop a notification
daemon, or modify Noctalia configuration. It reads the running Noctalia warning
threshold before enabling its optional controls. With Noctalia's default 10%
threshold, Niri Feel handles 15%, leaving the later warnings to Noctalia. If Noctalia already
covers the current level (or its live policy cannot be read), Niri Feel yields
the optional controls and shows only the brief aura. Existing critical warnings
remain owned by Noctalia. See [Noctalia's battery service documentation](https://docs.noctalia.dev/noctalia/services/battery/).

### Preview without draining the battery

```sh
./run --preview-low-battery
```

This simulates the low-battery aura; the terminal explicitly labels it as a
preview. As the aura fades, click the labelled **Options** control at the bottom
center within its eight-second availability window to reveal the simulated
controls. Try either priority, read its proposal, and use **Simulate apply**. **Replay aura** repeats the six-second aura
inside the same running application. The Preview stays open after the aura fades;
use **Dismiss** or Ctrl+C to exit. The preview never instantiates the real settings
adapter, writes the real alert latch, or touches session SQLite. It exits when
the experience is dismissed. Normal low-battery alerts retain their idle timeouts.
No settings are changed even after confirming a simulated action. No extra packages are needed.

## Network Recovery

```sh
./run --preview-network-recovery
```

The roughly 23-second Preview demonstrates an amber disconnection aura, a
simulated partial download, a short green reconnection aura, and a small recovery
view that fades naturally if ignored. All displayed download data is marked
**PREVIEW / SIMULATED**. **Open folder** is simulated too: it confirms the action
without opening a real folder. This mode creates no download files, changes no
network settings, and does not instantiate the real network or Downloads watcher.

For real events, leave the normal `./run` listener running. The feature listens
to NetworkManager's existing `State` and `Connectivity` D-Bus properties, with a
1.2-second debounce. It never calls `CheckConnectivity`, enables probes, reconnects
a network, or sends a request to a test server. NetworkManager may already perform
its own configured checks; Niri Feel only consumes their results. A connected link
with unknown Internet connectivity is not presented as proven Internet access.
The initial state is seeded quietly; daemon loss or unknown/sleep state breaks
correlation rather than creating a fake outage.

### Which downloads are considered?

GIO watches only the **top level** of the configured XDG Downloads directory
(falling back to `~/Downloads`). It observes metadata for `.part`, `.crdownload`
and `.aria2` files, plus changes to an adjacent aria2 payload. There is no recursive
scan, file-content read, browser-history access, URL extraction, or browser-profile
inspection. Symlink files are not followed. Paths and timestamps remain in bounded
memory; this feature writes no history, database, or telemetry.

The first scan is a baseline, not evidence of a failed download. A candidate must
have an **observed creation or size/mtime/allocation change within 30 seconds
before the observed disconnect, or its first 10 seconds**. A second metadata
comparison waits about four seconds after connectivity returns. Files that vanish,
change identity, or keep changing in that recovery window are not reported. Later
activity removes an already displayed hint. An old, untouched partial file is not
blamed on the outage.

When there is a candidate, the floating view shows its name and location, allocated disk
space, logical file length, an explicitly uncertain status, and a conditional
recovery suggestion. With several candidates, **Next** cycles through them.
**Open folder** opens the Downloads directory in the file manager only after a
click. There is no Resume button or automatic download action in this version.
The view fades after about 14 seconds without interaction. If no candidate was
identified, there is **no generic recovery popup**, only the green aura.

### Important detection limits

- A partial extension does not prove which application owns the file, that it is
  downloading, or that a network outage caused an interruption. The status is
  always **Possibly affected · app status unknown**, never a claim of failure.
- `st_size` is logical length and `st_blocks * 512` is allocated filesystem space.
  Neither proves how much valid payload has been downloaded. Sparse files and
  preallocation make this especially important. No percentage or expected total
  size is guessed.
- An `.aria2` file is a **control file**. Its own size is never shown as downloaded
  payload. When the adjacent payload is unavailable, data size is unavailable.
  An aria2 sidecar and a matching `.part` payload are deduplicated.
- Firefox/Chromium hints only suggest checking the original browser's Downloads
  interface for Resume/Retry. For aria2, the payload and control file should stay
  together and the original task should be checked. Server support, source URLs,
  credentials, and actual resume availability are not known to Niri Feel.
- Paused downloads, unrelated writes and delayed automatic retries can still
  produce false positives. Fast writes/retries, unsupported names, nested folders,
  and activity before this process started can be missed. A restart does not
  reconstruct earlier network events or download history.
- Monitoring is bounded to 5,000 directory entries per snapshot, 128 partials,
  256 pending paths and four metadata jobs. On overload or unavailable monitoring,
  evidence is discarded conservatively; the UI never claims complete coverage.
- Connectivity classification depends on what NetworkManager reports. Its checks
  may be disabled, stale or unable to distinguish a particular server failure.
  Networkd-only and other unsupported network stacks do not produce these auras.
- If Downloads is missing or cannot be monitored, it is not created. Connectivity
  animation still works; file-recovery hints are unavailable.

Network state, evidence (`network_model.py`) and GTK presentation are separate,
so a future explicitly authorized browser bridge can supply stronger task/resume
information without pretending file metadata already provides it. No browser
extension is implemented or required now.

References: [NetworkManager D-Bus states](https://networkmanager.pages.freedesktop.org/NetworkManager/libnm/libnm-nm-dbus-interface.html),
[GIO file monitoring](https://docs.gtk.org/gio/class.FileMonitor.html),
[aria2 manual](https://aria2.github.io/manual/en/html/aria2c.html).

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

To include the live GTK/Niri pointer-region regression (briefly shows a test
surface in the current desktop session):

```sh
LD_PRELOAD=libgtk4-layer-shell.so.0 GDK_BACKEND=wayland \
  NIRI_FEEL_GUI_TEST=1 python3 -m unittest discover -s tests -v
```

The live test checks that hidden Options controls cannot intercept the center
Brightness button. The complete Options → Choice → Confirmation flow has also
been exercised with actual Wayland pointer events in the isolated Preview, even
with the real battery at 100%. Network Recovery tests also cover NM state seeding,
old/growing/removed partials, metadata-only inspection, aria2 sidecars, sparse
files, real temporary-directory monitor events, and Preview isolation.

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

[Apache License, Version 2.0](LICENSE) (`Apache-2.0`).

Copyright © 2026 **Invar Gervi**, the original creator of Niri Feel.
See [NOTICE](NOTICE) for attribution and the
[project repository](https://github.com/InvarGervi123/niri-feel) for the source.

Commercial use, modification, and inclusion of Niri Feel code in proprietary
software are permitted, subject to the license conditions. Redistribution must
comply with Section 4, including supplying the license, marking modified files,
and retaining applicable copyright and attribution notices. Relevant NOTICE
attributions must be reproduced in one of the locations permitted by the license.

The license does **not** require creator attribution inside the application's
user interface or prior permission from the original creator. NOTICE adds no
extra conditions. Dependencies retain their respective licenses.

This license update does not retroactively revoke permissions already granted
for earlier copies of the project.
