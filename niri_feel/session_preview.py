"""Isolated, synthetic full-session preview. Never opens the real database."""
from dataclasses import replace
from .energy import Sample, Counter
from .sessions import Sessions, SessionStore

class PreviewSession:
    def __init__(self):
        self.store=SessionStore(":memory:")
        self.sessions=Sessions(self.store,"preview-boot")
        self.mono=0.; self.boot=0.; self.wh=39.6; self.energy=100_000_000
        self.sessions.feed(self.reading(True),wall=0)

    def reading(self,online):
        return Sample(self.mono,self.boot,(("SIMULATED",1,"preview"),),self.wh,
            self.wh/39.6*100,not online,
            {"intel-rapl:0":Counter(int(self.energy),262_143_328_850,("preview-package",1))},online)

    def unplug(self):
        self.mono+=1; self.boot+=1
        self.sessions.feed(self.reading(False),wall=self.boot)

    def collect(self):
        # 30 active minutes, with a 15-minute sleep in the middle. Virtual time.
        for index in range(120):
            if index==60:
                self.mono+=1; self.boot+=901; self.wh-=.06
                self.energy+=1_000_000
                self.sessions.feed(self.reading(False),wall=self.boot)
            self.mono+=15; self.boot+=15
            self.wh-=8*15/3600
            self.energy+=3.6*15*1e6
            self.sessions.feed(self.reading(False),wall=self.boot)

    def reconnect(self):
        self.mono+=1; self.boot+=1
        self.energy+=3.6*1e6
        result=self.sessions.feed(self.reading(True),wall=self.boot)
        result["preview"]=True
        return result

    def close(self):
        self.store.close()
