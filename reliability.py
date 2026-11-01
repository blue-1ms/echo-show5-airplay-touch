"""Bounded peer health, ordered controls, and explicit playback evidence."""
import math
import threading
import time

class PeerHealth:
    def __init__(self, clock=time.monotonic):
        self.clock=clock
        self.lock=threading.RLock()
        self.started=clock()
        self.last_success=None
        self.failures=0
        self.data={}
        self.error=''
    def success(self, data):
        with self.lock:
            self.last_success=self.clock()
            self.failures=0
            self.error=''
            self.data=dict(data)
    def failure(self, error):
        with self.lock:
            self.failures+=1
            self.error=error
    def snapshot(self):
        with self.lock:
            age=self.clock()-(self.last_success if self.last_success is not None else self.started)
            state='online' if self.last_success is not None and not self.failures else 'reconnecting'
            if self.failures>=3 and age>15:state='offline'
            return dict(self.data,status=state,error=self.error,failures=self.failures,
                        age=round(age,1),online=state=='online')

class OrderedControls:
    def __init__(self):
        self.lock=threading.RLock()
        self.seen={}
    def apply(self, request, callback, now=None):
        now=time.time() if now is None else now
        session=request.get('session')
        seq=request.get('seq')
        issued=request.get('issued')
        if not isinstance(session,str) or len(session)!=32 or any(c not in '0123456789abcdef' for c in session):
            raise ValueError('Invalid control session')
        if type(seq) is not int or not 0<seq<2**53 or type(issued) not in (int,float) or not math.isfinite(issued):
            raise ValueError('Invalid control sequence')
        if now-issued>5 or issued-now>5:raise ValueError('Expired control')
        with self.lock:
            self.seen={k:v for k,v in self.seen.items() if now-v[1]<60}
            if seq<=self.seen.get(session,(0,0))[0]:return False
            if len(self.seen)>=64 and session not in self.seen:raise ValueError('Too many control sessions')
            callback()
            self.seen[session]=(seq,now)
            return True

class PlaybackEvidence:
    def __init__(self):
        self.lock=threading.Lock()
        self.event=None
        self.rate_key=None
        self.rate=None
    def event_received(self, code):
        with self.lock:
            if code in ('paus','prsm','pbeg','pend'):self.event=code
    def resolve(self, active, reported, info, title):
        with self.lock:
            if not active:
                self.event=None;self.rate=None;self.rate_key=None
                return 'Stopped',None,'inactive'
            key=(str(info.get('kMRMediaRemoteNowPlayingInfoTimestamp','')),
                 str(info.get('kMRMediaRemoteNowPlayingInfoTitle','')),
                 info.get('kMRMediaRemoteNowPlayingInfoPlaybackRate'))
            raw=info.get('kMRMediaRemoteNowPlayingInfoPlaybackRate')
            valid=raw is not None and isinstance(raw,(int,float)) and math.isfinite(raw) and raw>=0 and key[1]==title
            if valid and key!=self.rate_key:
                self.rate_key=key;self.rate=float(raw);self.event=None
            if self.event=='paus':return 'Paused',None,'stream-pause'
            if self.event in ('prsm','pbeg'):return 'Playing',None,'stream-resume'
            if self.event=='pend' and not (valid and raw==0):return 'Unknown',None,'stream-ended'
            if valid:
                elapsed=info.get('kMRMediaRemoteNowPlayingInfoElapsedTime')
                return ('Paused' if raw==0 else 'Playing'),elapsed if raw==0 else None,'sender-rate'
            if reported in ('Playing','Paused'):return reported,None,'mpris'
            return 'Unknown',None,'unconfirmed'
