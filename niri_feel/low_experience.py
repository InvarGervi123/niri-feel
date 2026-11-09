"""Coordinate a once-per-cycle alert. Choosing never applies; confirming does."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import time
from gi.repository import Gdk, GLib
from .low_battery import LowLatch, Capabilities, propose, apply
from .low_controls import SystemPort, noctalia_owns
from .low_visual import LowWindow, install_style

class LowExperience:
    def __init__(self,app,preview=False,finished=lambda:None):
        self.app=app
        self.preview=preview
        self.finished=finished
        self.windows=[]
        self.timers=set()
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix="niri-feel-power")
        self.port=None if preview else SystemPort()
        state=Path(os.environ.get("XDG_STATE_HOME",Path.home()/".local/state"))/"niri-feel/low-battery.json"
        self.latch=LowLatch(None if preview else state)
        self.proposal=None
        self.generation=0
        self.closed=False
        self.expiry=0
        self.valid=False
        self.intent=False
        install_style(Gdk.Display.get_default())

    def later(self,ms,callback):
        def fire():
            self.timers.discard(timer)
            callback()
            return False
        timer=GLib.timeout_add(ms,fire)
        self.timers.add(timer)
        return timer

    def expire(self,ms):
        if self.expiry in self.timers:
            GLib.source_remove(self.expiry); self.timers.discard(self.expiry)
        self.expiry=0 if self.preview else self.later(ms,self.dismiss)

    def work(self,operation,callback):
        generation=self.generation
        future=self.pool.submit(operation)
        def done(future):
            try:
                result,error=future.result(),None
            except ValueError as failure:
                result,error=None,str(failure)
            except Exception:
                result,error=None,"System request unavailable. Check current settings before retrying."
            def deliver():
                if not self.closed and generation==self.generation:
                    callback(result,error)
                return False
            GLib.idle_add(deliver)
        future.add_done_callback(done)

    def update(self,online,battery):
        self.valid=(online is False and battery is not None and battery.state==2
            and isinstance(battery.percentage,(int,float)) and 0<=battery.percentage<=15
            and 0<=time.time()-battery.updated<=120)
        if self.valid:
            self.percent=battery.percentage
        trigger=self.latch.update(online,battery)
        if not self.valid:
            self.dismiss()
        elif trigger:
            percent=battery.percentage
            # Let the original disconnect light finish before showing the low glow.
            self.later(3600,lambda:self.policy(percent))

    def policy(self,percent):
        if not self.valid:
            return
        percent=self.percent
        self.work(lambda:noctalia_owns(percent),
            lambda owned,error:self.show(percent,with_card=not (owned or error)))

    def show(self,percent=15,with_card=True):
        if not self.preview and not self.valid:
            return
        monitors=Gdk.Display.get_default().get_monitors()
        items=[monitors.get_item(i) for i in range(monitors.get_n_items())]
        primary=next((m for m in items if (m.get_connector() or "").startswith("eDP")),items[0] if items else None)
        for monitor in items:
            self.windows.append(LowWindow(self.app,monitor,self,with_card and monitor==primary))
        self.percent=percent
        self.intent=False
        if self.preview:
            print("Preview · 6-second simulated aura. As it fades, the bottom-center Options button appears for eight seconds. Click it for choices or Replay aura. Dismiss or Ctrl+C to exit.",flush=True)
        self.expire(10000 if with_card else 3400)

    def card(self,title,body,buttons):
        for window in self.windows:
            window.show_card(title,body,buttons)

    def reveal(self):
        if not self.windows or self.intent:
            return
        self.intent=True
        self.choices()

    def choices(self):
        if not self.intent:
            return
        self.proposal=None
        self.expire(10000)
        prefix="Preview · simulated" if self.preview else ""
        actions=[("Performance",lambda:self.choose("Performance")),
                 ("Brightness",lambda:self.choose("Brightness"))]
        if self.preview:
            actions.append(("Replay aura",self.replay))
        actions.append(("Dismiss",self.dismiss))
        self.card(prefix,"",actions)

    def replay(self):
        if not self.preview or self.closed:
            return
        self.dismiss(finish_preview=False)
        self.show(15)


    def choose(self,choice):
        if not self.intent:
            return
        self.proposal=None
        self.expire(30000)
        self.card("Preview · checking options" if self.preview else "Checking supported options", "",[])
        def prepare():
            current=(Capabilities(True,"balanced",("balanced","performance","power-saver"),(),
                "simulated-display",100,100,True) if self.preview else self.port.read())
            return propose(choice,current,self.preview)
        def ready(proposal,error):
            if error:
                self.card("Preview · unavailable" if self.preview else "No change available",error,[("Back",self.choices),("Dismiss",self.dismiss)])
                return
            self.proposal=proposal
            self.card(("Preview · " if self.preview else "")+choice,proposal.explanation,
                [("Simulate apply" if self.preview else "Apply change",self.confirm),("Cancel",self.choices)])
        self.work(prepare,ready)

    def confirm(self):
        if not self.intent or self.proposal is None:
            return
        proposal,self.proposal=self.proposal,None
        self.card("Preview · simulating" if self.preview else "Applying your choice","",[])
        self.expire(30000)
        def done(result,error):
            self.card("Preview · finished" if self.preview else ("Review needed" if error else "Done"),
                error or result,[("Replay aura",self.replay),("Dismiss",self.dismiss)] if self.preview else [("Dismiss",self.dismiss)])
            self.expire(3500)
        self.work(lambda:apply(proposal,self.port,confirmed=True),done)

    def dismiss(self,finish_preview=True):
        self.generation+=1
        for timer in self.timers:
            GLib.source_remove(timer)
        self.timers.clear(); self.expiry=0
        for window in self.windows:
            window.stop()
        had_windows=bool(self.windows)
        self.windows=[]; self.proposal=None; self.intent=False
        if self.preview and had_windows and finish_preview:
            self.finished()

    def close(self):
        self.closed=True
        self.dismiss()
        self.pool.shutdown(wait=False,cancel_futures=True)
