"""Low-battery latch and explicit, one-shot power choices. No UI dependencies."""
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import time


class LowLatch:
    def __init__(self, path=None):
        self.path=Path(path) if path else None
        self.latched=False
        if self.path:
            try:
                self.latched=bool(json.loads(self.path.read_text())["latched"])
            except (OSError,ValueError,KeyError,TypeError):
                pass

    def save(self):
        if not self.path:
            return
        try:
            self.path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            temp=self.path.with_suffix(".tmp")
            fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
            with os.fdopen(fd,"w") as stream:
                json.dump({"latched":self.latched},stream)
            os.replace(temp,self.path)
        except OSError as error:
            print(f"Low battery: alert state could not be saved: {error}",flush=True)

    def update(self, online, battery, now=None):
        now=time.time() if now is None else now
        if battery is None:
            return False
        value=battery.percentage
        if (not isinstance(value,(int,float)) or isinstance(value,bool)
                or not math.isfinite(value) or not 0<=value<=100
                or not 0<=now-battery.updated<=120):
            return False
        if value>=20 and self.latched:
            self.latched=False; self.save()
        if online is False and battery.state==2 and value<=15 and not self.latched:
            self.latched=True; self.save()
            return True
        return False


@dataclass(frozen=True)
class Capabilities:
    on_battery: bool
    profile: str | None
    profiles: tuple
    holds: tuple
    device: str | None
    brightness: int | None
    maximum: int | None
    brightness_supported: bool


@dataclass(frozen=True)
class Proposal:
    choice: str
    baseline: Capabilities
    target: int | str
    explanation: str
    preview: bool=False


def propose(choice, current, preview=False):
    if not current.on_battery:
        raise ValueError("Available while running on battery only.")
    if choice=="Performance":
        if (not current.brightness_supported or current.device is None
                or not current.maximum or current.brightness is None or current.brightness<=1):
            raise ValueError("Internal-display dimming is not available through logind.")
        target=max(1,int(current.brightness*.8))
        before=100*current.brightness/current.maximum
        after=100*target/current.maximum
        return Proposal(choice,current,target,
            f"Keep the CPU profile unchanged. Dim the internal screen from {before:.0f}% to {after:.0f}%.",preview)
    if choice=="Brightness":
        if "power-saver" not in current.profiles or current.profile is None:
            raise ValueError("Power Saver is not supported by the current power service.")
        if current.holds:
            raise ValueError("Another application is holding a power profile. No override will be made.")
        if current.profile=="power-saver":
            raise ValueError("Power Saver is already active. Nothing needs to change.")
        return Proposal(choice,current,"power-saver",
            f"Keep screen brightness unchanged. Switch {current.profile} to power-saver. CPU performance may decrease.",preview)
    raise ValueError("Unsupported choice.")


def apply(proposal, port, confirmed=False):
    if confirmed is not True:
        raise ValueError("Explicit confirmation is required.")
    if proposal.preview:
        return "Preview only · no settings changed."
    current=port.read()
    if current!=proposal.baseline:
        raise ValueError("System settings changed. Please review the choice again.")
    # Revalidate support and conflict checks immediately before the one-shot write.
    checked=propose(proposal.choice,current)
    if checked.target!=proposal.target:
        raise ValueError("The proposed change is no longer available.")
    if proposal.choice=="Performance":
        port.set_brightness(current.device,proposal.target)
        return "Screen dimmed. CPU profile kept."
    port.set_profile(proposal.target)
    return "Power Saver enabled. Brightness kept."
