"""Network/partial-file evidence only. Never reads payloads or browser state."""
from dataclasses import dataclass
from pathlib import Path
import os
import stat

RECENT_SECONDS=30
DISCONNECT_GRACE=10
MAX_PARTIALS=128
MAX_DIRECTORY_ENTRIES=5000


def internet_state(state, connectivity):
    if state in (None,0,10):
        return None  # unknown/asleep is not a measured outage
    if state<50:
        return False
    if connectivity==4:
        return True
    if connectivity in (1,2,3):
        return False
    return None  # a connected link alone does not prove Internet reachability


class NetworkEdges:
    def __init__(self): self.previous=None
    def update(self,online):
        previous,self.previous=self.previous,online
        if previous is None or online is None or previous==online: return None
        return "online" if online else "offline"


@dataclass(frozen=True)
class Partial:
    marker: Path
    payload: Path | None
    kind: str
    identity: tuple
    signature: tuple
    length: int | None
    allocated: int | None


def kind_for(path):
    for suffix,kind in ((".crdownload","chromium"),(".aria2","aria2"),(".part","part")):
        if path.name.endswith(suffix): return kind
    return None


def regular_stat(path):
    try:
        value=os.stat(path,follow_symlinks=False)
        return value if stat.S_ISREG(value.st_mode) else None
    except OSError:
        return None


def inspect_partial(path):
    """lstat only. aria2's sidecar is metadata, never downloaded payload size."""
    path=Path(path); kind=kind_for(path)
    marker=regular_stat(path)
    if kind is None or marker is None: return None
    payload=Path(str(path)[:-6]) if kind=="aria2" else path
    data=regular_stat(payload)
    identity=(marker.st_dev,marker.st_ino,
              (data.st_dev,data.st_ino) if data else None)
    signature=(identity,marker.st_size,marker.st_mtime_ns,marker.st_blocks,
               (data.st_size,data.st_mtime_ns,data.st_blocks) if data else None)
    return Partial(path,payload if data else None,kind,identity,signature,
                   data.st_size if data else None,data.st_blocks*512 if data else None)


def scan_partials(directory):
    found=[]
    try:
        with os.scandir(directory) as entries:
            for index,entry in enumerate(entries):
                if index>=MAX_DIRECTORY_ENTRIES or len(found)>=MAX_PARTIALS: break
                path=Path(entry.path)
                if kind_for(path):
                    item=inspect_partial(path)
                    if item: found.append(item)
    except OSError:
        pass
    return found


@dataclass(frozen=True)
class RecoveryItem:
    partial: Partial
    status: str="Possibly affected · app status unknown"


def recovery_tip(kind):
    if kind=="chromium":
        return "If this belongs to a Chromium browser, check its Downloads page for Resume or Retry. Availability is not known here."
    if kind=="aria2":
        return "Keep the payload and .aria2 control file together. Check the original aria2 task. Resume support and the original source are not known here."
    return "If this belongs to Firefox, check its Downloads panel for Resume or Retry. A .part file alone does not prove it can resume."


class DownloadEvidence:
    def __init__(self):
        self.entries={}
        self.activity={}
        self.offline_at=None
        self.candidates={}
        self.returned={}
        self.visible={}

    def seed(self,partials):
        for item in partials:
            if len(self.entries)>=MAX_PARTIALS: break
            self.entries.setdefault(item.marker,item)

    def observe(self,path,item,now):
        path=Path(path)
        old=self.entries.get(path)
        if item is None:
            self.entries.pop(path,None); self.activity.pop(path,None)
            self.candidates.pop(path,None); self.returned.pop(path,None); self.visible.pop(path,None)
            return
        if old is None and len(self.entries)>=MAX_PARTIALS: return
        self.entries[path]=item
        if old is None or old.signature!=item.signature:
            self.activity[path]=now
            self.visible.pop(path,None)
            if (self.offline_at is not None and
                    self.offline_at-RECENT_SECONDS<=now<=self.offline_at+DISCONNECT_GRACE):
                self.candidates[path]=item.identity

    def disconnected(self,now):
        self.offline_at=now; self.returned={}; self.visible={}
        self.candidates={path:item.identity for path,item in self.entries.items()
                         if now-RECENT_SECONDS<=self.activity.get(path,float('-inf'))<=now}

    def reconnected(self,partials):
        self.returned={item.marker:item for item in partials
                       if self.candidates.get(item.marker)==item.identity}

    def settled(self,partials):
        after={item.marker:item for item in partials}
        self.visible={}
        for path,before in self.returned.items():
            item=after.get(path)
            if item and item.identity==before.identity and item.signature==before.signature:
                self.visible[path]=RecoveryItem(item)
        self.offline_at=None; self.candidates={}; self.returned={}
        return self.items()

    def items(self):
        # A .part payload with an aria2 sidecar is one item, not two downloads.
        result=[]; seen=set()
        ordered=sorted(self.visible.values(),key=lambda item:item.partial.kind!="aria2")
        for item in ordered:
            key=item.partial.payload or item.partial.marker
            if key not in seen:
                seen.add(key); result.append(item)
        return result[:MAX_PARTIALS]

    def cancel(self):
        self.offline_at=None; self.candidates={}; self.returned={}; self.visible={}
