"""Persistent touch preferences and device-local sleep/volume policy."""
import json,math,os,threading,time
from pathlib import Path

DEFAULTS=dict(layout='artwork',idle_clock=True,night_start=22,night_end=7,volume_limit=100)

def validated(values):
    if not isinstance(values,dict) or set(values)-set(DEFAULTS):raise ValueError('Unknown setting')
    out=dict(DEFAULTS,**values)
    if out['layout'] not in ('artwork','large-text'):raise ValueError('Invalid layout')
    if type(out['idle_clock']) is not bool:raise ValueError('Invalid clock preference')
    for name in ('night_start','night_end'):
        if type(out[name]) is not int or not 0<=out[name]<=23:raise ValueError('Invalid night hour')
    if type(out['volume_limit']) is not int or not 0<=out['volume_limit']<=100:raise ValueError('Invalid output limit')
    return out

class Preferences:
    def __init__(self,path,gain,pause,clock=time.time):
        self.path=Path(path);self.gain=gain;self.pause=pause;self.clock=clock
        self.lock=threading.RLock();self.settings=dict(DEFAULTS);self.timer=None
        self.applied=None;self.error='';self.last_apply=0
        if self.path.exists():
            data=json.loads(self.path.read_text(encoding='utf-8'))
            self.settings=validated(data['settings']);self.timer=data.get('timer')
    def save(self):
        tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(dict(settings=self.settings,timer=self.timer)),encoding='utf-8')
        os.chmod(tmp,0o600);tmp.replace(self.path)
    def snapshot(self):
        with self.lock:
            timer=dict(self.timer) if self.timer else None
            if timer:timer['remaining']=max(0,round(timer['deadline']-self.clock()))
            return dict(settings=dict(self.settings),sleep=timer,output_error=self.error)
    def update(self,values):
        with self.lock:
            settings=validated(dict(self.settings,**values))
            target=self.target(settings=settings)
            self.gain(target)
            self.applied=target;self.last_apply=self.clock();self.error=''
            self.settings=settings;self.save()
    def start(self,minutes=None,deadline=None,pause=True):
        with self.lock:
            if deadline is None:
                if type(minutes) is not int or not 1<=minutes<=180:raise ValueError('Choose 1–180 minutes')
                deadline=self.clock()+minutes*60
            if type(deadline) not in (float,int) or not math.isfinite(deadline) or not self.clock()<deadline<=self.clock()+10801:raise ValueError('Invalid sleep deadline')
            self.timer=dict(deadline=deadline,fade=min(60,deadline-self.clock()),finished=False,pause=bool(pause))
            self.save()
    def cancel(self):
        with self.lock:
            self.gain(self.settings['volume_limit'])
            self.applied=self.settings['volume_limit'];self.last_apply=self.clock()
            self.timer=None;self.error='';self.save()
    def target(self,settings=None):
        limit=(settings or self.settings)['volume_limit']
        if not self.timer:return limit
        if self.timer.get('finished'):return 0
        remaining=self.timer['deadline']-self.clock()
        return max(0,min(limit,round(limit*remaining/max(1,self.timer['fade']),1)))
    def tick(self):
        with self.lock:
            target=self.target()
            try:
                if target!=self.applied or self.clock()-self.last_apply>=30:
                    self.gain(target);self.applied=target;self.last_apply=self.clock()
                if self.timer and not self.timer['finished'] and self.clock()>=self.timer['deadline']:
                    self.timer['finished']=True;self.save()
                    if self.timer['pause']:
                        try:self.pause()
                        except Exception:
                            self.timer['pause_failed']=True;self.save()
                            raise
                if self.timer and self.timer.get('pause_failed'):
                    self.error='This Echo is muted, but the iPhone did not accept pause. Use your iPhone.'
                else:self.error=''
            except Exception:
                self.error='Audio control unavailable. Check the receiver; sleep may not have paused your iPhone.'
