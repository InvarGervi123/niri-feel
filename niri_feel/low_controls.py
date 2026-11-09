"""Existing D-Bus capabilities only. All slow operations run off the GTK thread."""
from pathlib import Path
import shutil
import subprocess
from gi.repository import Gio, GLib
from .low_battery import Capabilities

PP="org.freedesktop.UPower.PowerProfiles"
PP_PATH="/org/freedesktop/UPower/PowerProfiles"
SESSION="/org/freedesktop/login1/session/auto"

class SystemPort:
    def call(self,destination,path,interface,method,args=None):
        bus=Gio.bus_get_sync(Gio.BusType.SYSTEM,None)
        return bus.call_sync(destination,path,interface,method,args,None,
            Gio.DBusCallFlags.NO_AUTO_START,1500,None).unpack()

    def read(self):
        root=self.call("org.freedesktop.UPower","/org/freedesktop/UPower",
            "org.freedesktop.DBus.Properties","GetAll",GLib.Variant("(s)",("org.freedesktop.UPower",)))[0]
        session=self.call("org.freedesktop.login1",SESSION,"org.freedesktop.DBus.Properties",
            "GetAll",GLib.Variant("(s)",("org.freedesktop.login1.Session",)))[0]
        if session.get("LockedHint",True) or not session.get("Active",False):
            raise ValueError("Unlock the active session before reviewing power choices.")
        try:
            props=self.call(PP,PP_PATH,"org.freedesktop.DBus.Properties","GetAll",GLib.Variant("(s)",(PP,)))[0]
        except GLib.Error:
            props={}
        devices=sorted(Path("/sys/class/backlight").glob("*"))
        device=brightness=maximum=None
        supported=False
        if len(devices)==1:
            try:
                path=devices[0]
                brightness=int((path/"brightness").read_text())
                maximum=int((path/"max_brightness").read_text())
                xml=self.call("org.freedesktop.login1",SESSION,
                    "org.freedesktop.DBus.Introspectable","Introspect")[0]
                supported='name="SetBrightness"' in xml and 0<=brightness<=maximum
                device=path.name
            except (OSError,ValueError,GLib.Error):
                pass
        return Capabilities(root.get("OnBattery") is True,props.get("ActiveProfile"),
            tuple(sorted(p["Profile"] for p in props.get("Profiles",[]) if "Profile" in p)),
            tuple(str(h) for h in props.get("ActiveProfileHolds",[])),
            device,brightness,maximum,supported)

    def set_brightness(self,device,value):
        self.call("org.freedesktop.login1",SESSION,"org.freedesktop.login1.Session",
            "SetBrightness",GLib.Variant("(ssu)",("backlight",device,value)))

    def set_profile(self,value):
        self.call(PP,PP_PATH,"org.freedesktop.DBus.Properties","Set",
            GLib.Variant("(ssv)",(PP,"ActiveProfile",GLib.Variant("s",value))))


def noctalia_owns(percent):
    """Read the live shell policy, never change it or send duplicate notifications."""
    server=None
    try:
        bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
        server=bus.call_sync("org.freedesktop.Notifications","/org/freedesktop/Notifications",
            "org.freedesktop.Notifications","GetServerInformation",None,None,
            Gio.DBusCallFlags.NO_AUTO_START,800,None).unpack()[0]
        if "noctalia" not in server.lower():
            return False
        if not shutil.which("noctalia"):
            return True
        result=subprocess.run(["noctalia","msg","config-get","battery.warning_threshold"],
            capture_output=True,text=True,timeout=1,check=True)
        threshold=float(result.stdout.strip())
        return threshold>0 and (percent<=threshold or percent<=5)
    except (GLib.Error,OSError,ValueError,subprocess.SubprocessError):
        # Yield only when a known Noctalia instance has unreadable policy.
        return server is not None and "noctalia" in server.lower()
