#!/usr/bin/env python3
"""Local-only touch companion for Shairport Sync (no external dependencies but dbus)."""
import hashlib
import json
import math
import mimetypes
import secrets
import hmac
import threading
import time
import os
import re
from receiver import receiver_lock, restart_receiver
import unicodedata
from preferences import Preferences, validated
from local_audio import set_output
from pairing import Pairing
import logging
from logging.handlers import RotatingFileHandler
from urllib.error import HTTPError
from reliability import PeerHealth, OrderedControls, PlaybackEvidence
from urllib.request import Request, urlopen, ProxyHandler, build_opener
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote, urlparse
import dbus

ROOT = Path(__file__).resolve().parent
ART_ROOT = Path(os.environ.get('SHAIRPORT_TOUCH_ART_DIR', '/run/echo-airplay/coverart')).resolve()
ORIGIN = 'http://127.0.0.1:8765'
TOKEN = secrets.token_urlsafe(32)
IFACE = 'org.mpris.MediaPlayer2.Player'
PROPS = 'org.freedesktop.DBus.Properties'
thread_data = threading.local()
PAIR_PATH = ROOT / 'pair.json'
PAIR = json.loads(PAIR_PATH.read_text()) if PAIR_PATH.exists() else {}
PAIR_LOCK = threading.Lock()
PEER = {'online': False}
peer_address = ('', 0)

def system_bus():
    if not hasattr(thread_data, 'bus') or not thread_data.bus.get_is_connected():
        thread_data.bus = dbus.SystemBus(private=True)
    return thread_data.bus

def set_link(enabled):
    with PAIR_LOCK:
        PAIR['linked'] = bool(enabled)
        tmp = PAIR_PATH.with_suffix('.tmp')
        tmp.write_text(json.dumps(PAIR))
        os.chmod(tmp, 0o600)
        tmp.replace(PAIR_PATH)

HEALTH = PeerHealth()
OUTBOUND_LOCK = threading.Lock()
CONTROL_ORDER = OrderedControls()
CONTROL_SESSION = secrets.token_hex(16)
control_sequence = 0
PLAYBACK = PlaybackEvidence()
STATE_LOCK = threading.Lock()
STATE_CACHE = {}
LOG = logging.getLogger('echo-diagnostics')
LOG.addHandler(logging.NullHandler())

PREFERENCES=None
PAIRING=None

def commit_pair(values):
    global peer_address,HEALTH
    with PAIR_LOCK:
        tmp=PAIR_PATH.with_suffix('.tmp');tmp.write_text(json.dumps(values));os.chmod(tmp,0o600);tmp.replace(PAIR_PATH)
        PAIR.clear();PAIR.update(values)
        peer_address=('',0);HEALTH=PeerHealth()

def pause_sender():
    state=read_state()
    if state['active']:
        _,_,player=interfaces();player.Pause(timeout=3)

def feature_state():
    if not PREFERENCES:return {}
    return dict(PREFERENCES.snapshot(),pairing=PAIRING.status(),device_id=PAIRING.identity)

def feature_worker():
    while True:
        PREFERENCES.tick()
        try:PAIRING.advertise();PAIRING.poll()
        except Exception as error:LOG.info('pairing service %s',type(error).__name__)
        time.sleep(1)

def feature_action(data):
    action=data.get('action')
    if action=='preferences':PREFERENCES.update(data['values'])
    elif action=='sleep':
        PREFERENCES.start(minutes=data.get('minutes'),pause=True)
        warning=None
        if data.get('both'):
            try:
                if 'sleep-v1' not in HEALTH.snapshot().get('features',[]):raise ValueError()
                peer_call('sleep',deadline=PREFERENCES.snapshot()['sleep']['deadline'])
            except Exception:warning='Timer started only here. Peer unavailable or needs an update.'
        return dict(ok=True,warning=warning,**feature_state())
    elif action=='sleep_cancel':
        PREFERENCES.cancel()
        if data.get('both'):
            try:peer_call('sleep_cancel')
            except Exception:return dict(ok=True,warning='Cancelled here. Cancel the timer on your peer too.',**feature_state())
    elif action=='pair_open':PAIRING.open()
    elif action=='pair_scan':return dict(ok=True,devices=PAIRING.scan())
    elif action=='pair_start':PAIRING.start(data['id'])
    elif action=='pair_confirm':PAIRING.confirm(data['code'])
    elif action=='unpair':
        warning=None
        try:peer_call('unpair')
        except Exception:warning='Removed here. Remove pairing on the other device too if it is offline.'
        commit_pair({})
        return dict(ok=True,warning=warning,**feature_state())
    elif action=='backup':
        backup=dict(format='echo-airplay-touch',version=1,device_id=PAIRING.identity,name=read_state()['name'],settings=PREFERENCES.snapshot()['settings'])
        if data.get('include_pair'):
            with PAIR_LOCK:backup['pair']=dict(PAIR)
        return dict(ok=True,backup=backup)
    elif action=='restore':
        backup=data['backup']
        if not isinstance(backup,dict) or backup.get('format')!='echo-airplay-touch' or backup.get('version')!=1:raise ValueError('Unsupported backup')
        settings=validated(backup['settings']);name=backup['name']
        renamed_config(CONFIG_PATH.read_text(),name)
        pair=None
        if data.get('include_pair') and 'pair' in backup:
            if backup.get('device_id')!=PAIRING.identity:raise ValueError('Pairing can only be restored to its original device. Restore settings only instead.')
            pair=backup['pair']
            if not isinstance(pair,dict):raise ValueError('Invalid pairing backup')
            if pair and (set(pair)-set(('self_service','peer_service','peer_name','secret','linked')) or pair.get('self_service')!=PAIRING.identity or not re.fullmatch('[0-9a-f]{64}',pair.get('secret','')) or type(pair.get('linked')) is not bool or not isinstance(pair.get('peer_service'),str) or not 1<=len(pair['peer_service'])<=100 or not isinstance(pair.get('peer_name',''),str) or len(pair.get('peer_name',''))>80):raise ValueError('Invalid pairing backup')
        previous=PREFERENCES.snapshot()['settings']
        PREFERENCES.update(settings)
        try:rename_receiver(name)
        except Exception:PREFERENCES.update(previous);raise
        if pair is not None:commit_pair(pair)
        return dict(ok=True,warning='Settings restored. Reselect this receiver in AirPlay if its name changed.',**feature_state())
    else:return None
    return dict(ok=True,**feature_state())


def request_peer(address, request):
    data=json.dumps(request,separators=(',',':')).encode()
    stamp=str(int(time.time()));nonce=secrets.token_hex(16)
    signature=hmac.new(PAIR['secret'].encode(),stamp.encode()+b'\n'+nonce.encode()+b'\n'+data,hashlib.sha256).hexdigest()
    req=Request('http://'+address+':8766/peer',data=data,headers={'Content-Type':'application/json','X-Echo-Time':stamp,'X-Echo-Nonce':nonce,'X-Echo-Signature':signature})
    with build_opener(ProxyHandler({})).open(req,timeout=3) as response:
        payload=response.read(16385)
        if len(payload)>16384:raise ValueError('Oversized response')
        result=json.loads(payload)
        if result.get('protocol',0)>=2:
            expected=hmac.new(PAIR['secret'].encode(),nonce.encode()+b'\n'+payload,hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected,response.headers.get('X-Echo-Signature','')):
                raise PermissionError('Invalid peer response signature')
        elif request['action']!='state':
            raise PermissionError('Peer protocol upgrade required')
        return result

def peer_call(action, **values):
    global peer_address, control_sequence
    with OUTBOUND_LOCK:
        if not PAIR.get('secret'):raise RuntimeError('Unpaired')
        if action!='state' and HEALTH.snapshot().get('protocol',0)<2:
            raise RuntimeError('Update both receivers to use reliable volume linking.')
        cached,checked=peer_address
        address=cached
        if not address or time.monotonic()-checked>30:
            try:
                avahi=dbus.Interface(system_bus().get_object('org.freedesktop.Avahi','/'),'org.freedesktop.Avahi.Server')
                result=avahi.ResolveService(-1,0,PAIR['peer_service'],'_echo-volume._tcp','local',0,0,timeout=2)
                address=str(result[7])
            except Exception as error:
                LOG.info('peer discovery failed type=%s cached_address=%s',type(error).__name__,bool(cached))
                if not cached:
                    HEALTH.failure('discovery')
                    raise
        request=dict(action=action,**values)
        if action!='state':
            control_sequence+=1
            request.update(session=CONTROL_SESSION,seq=control_sequence,issued=time.time())
        candidates=[address]
        # Only a read-only health probe may try a second address. Controls are
        # never queued or automatically replayed after an uncertain result.
        if action=='state' and cached and cached!=address:candidates.append(cached)
        last_error=None
        for candidate in candidates:
            try:
                result=request_peer(candidate,request)
                peer_address=(candidate,time.monotonic())
                HEALTH.success(result);PEER.update(result,online=True)
                if action!='state' and not result.get('ready',True):
                    raise RuntimeError('Peer receiver reconnecting')
                return result
            except RuntimeError:raise
            except Exception as error:
                last_error=error
                LOG.info('peer attempt failed action=%s type=%s detail=%s',action,type(error).__name__,str(error)[:160])
                if isinstance(error,(PermissionError,HTTPError,ValueError)):
                    break
        if isinstance(last_error,HTTPError):
            kind='authentication' if last_error.code in (401,403) else ('receiver' if last_error.code==503 else 'protocol')
        else:
            kind='authentication' if isinstance(last_error,PermissionError) else ('protocol' if isinstance(last_error,ValueError) else 'network')
        HEALTH.failure(kind)
        peer_address=(cached,0)
        raise last_error


def monitor_peer():
    group = None
    while True:
        if not PAIR.get('secret'):
            if group is not None:
                try:group.Free(timeout=2)
                except Exception:pass
                group=None
            time.sleep(2);continue
        try:
            group = maintain_pair_service(group)
        except Exception:
            group = None
        try:
            peer_call('state')
        except Exception:
            pass
        time.sleep(5)

def maintain_pair_service(group):
    # A reachable EntryGroup is not necessarily advertised. Avahi may reset it
    # after host-name conflict resolution, interface changes, or daemon restart.
    if group is not None:
        try:
            state = int(group.GetState(timeout=2))
            if state in (1, 2):  # REGISTERING or ESTABLISHED
                return group
        except Exception:
            pass
        try:
            group.Free(timeout=2)
        except Exception:
            pass
    avahi = dbus.Interface(system_bus().get_object('org.freedesktop.Avahi', '/'), 'org.freedesktop.Avahi.Server')
    if int(avahi.GetState(timeout=2)) != 2:  # Wait until the host name is stable.
        return None
    return publish_pair_service()

def publish_pair_service():
    connection = system_bus()
    avahi = dbus.Interface(connection.get_object('org.freedesktop.Avahi', '/'), 'org.freedesktop.Avahi.Server')
    group = dbus.Interface(connection.get_object('org.freedesktop.Avahi', avahi.EntryGroupNew()), 'org.freedesktop.Avahi.EntryGroup')
    try:
        group.AddService(-1, 0, dbus.UInt32(0), PAIR['self_service'], '_echo-volume._tcp', 'local', '', dbus.UInt16(8766), dbus.Array([], signature='ay'))
        group.Commit()
    except Exception:
        try:
            group.Free(timeout=2)
        except Exception:
            pass
        raise
    return group

def interfaces():
    bus = system_bus()
    core = bus.get_object('org.gnome.ShairportSync', '/org/gnome/ShairportSync')
    player = bus.get_object('org.mpris.MediaPlayer2.ShairportSync', '/org/mpris/MediaPlayer2')
    return dbus.Interface(core, PROPS), dbus.Interface(player, PROPS), dbus.Interface(player, IFACE)

def artwork_path(url):
    parsed = urlparse(str(url))
    if parsed.scheme != 'file' or parsed.netloc not in ('', 'localhost'):
        return None
    path = Path(unquote(parsed.path)).resolve()
    if not path.is_relative_to(ART_ROOT) or not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
        return None
    if path.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp'):
        return None
    return path

def collect_state():
    core, props, _ = interfaces()
    c = core.GetAll('org.gnome.ShairportSync', timeout=3)
    p = props.GetAll(IFACE, timeout=3)
    m = p.get('Metadata', {})
    try:
        info=core.Get('org.gnome.ShairportSync.Client','NowPlayingInformation',timeout=1)
    except Exception:
        info={}
    effective, paused_position, evidence=PLAYBACK.resolve(bool(c.get('Active',False)),str(p.get('PlaybackStatus','')),info,str(m.get('xesam:title','')))
    peer=HEALTH.snapshot()
    try:
        raw_volume=float(core.Get('org.gnome.ShairportSync.RemoteControl','AirplayVolume',timeout=1))
    except Exception:
        raw_volume=None
    active = bool(c.get('Active', False))
    art = artwork_path(m.get('mpris:artUrl', '')) if active else None
    volume = max(0, min(100, round(float(p.get('Volume', 0)) * 100)))
    duration = max(0, float(m.get('mpris:length', 0)) / 1e6)
    position = max(0, float(p.get('Position', 0)) / 1e6)
    if paused_position is not None:
        try:
            if math.isfinite(float(paused_position)):position=max(0,float(paused_position))
        except (ValueError,TypeError):pass
    return dict(ok=True, raw_volume=raw_volume, state_source=evidence, peer_status=peer['status'], peer_error=peer['error'], peer_ready=peer.get('ready',False), peer_protocol=peer.get('protocol',0), name=str(c.get('ServiceName', 'Echo AirPlay')), active=active,
        state=effective,
        title=str(m.get('xesam:title', '')) if active else '',
        artist=' · '.join(map(str, m.get('xesam:artist', []))) if active else '',
        album=str(m.get('xesam:album', '')) if active else '',
        duration=duration if active else 0, position=min(position, duration) if duration else position,
        volume=volume, art=hashlib.sha256(str(art).encode()).hexdigest()[:20] if art else '',
        can_toggle=active and effective in ('Playing','Paused') and bool(p.get('CanControl')) and bool(p.get('CanPause') if effective == 'Playing' else p.get('CanPlay')),
        can_next=active and bool(p.get('CanGoNext')), can_previous=active and bool(p.get('CanGoPrevious')),
        paired=bool(PAIR.get('secret')), linked=bool(PAIR.get('linked')),
        peer_online=peer['online'], peer_volume=peer.get('volume'), peer_name=peer.get('name') or PAIR.get('peer_name', ''))

def read_state():
    with STATE_LOCK:
        cached=dict(STATE_CACHE)
    if cached:
        if time.monotonic()-cached.pop('_sampled')>3:
            raise RuntimeError('Receiver state stale')
        peer=HEALTH.snapshot()
        cached.update(paired=bool(PAIR.get('secret')),linked=bool(PAIR.get('linked')),peer_status=peer['status'],peer_error=peer['error'],peer_ready=peer.get('ready',False),peer_protocol=peer.get('protocol',0),peer_online=peer['online'],peer_volume=peer.get('volume'),peer_name=peer.get('name') or PAIR.get('peer_name',''))
        return cached
    return collect_state()

def sample_state():
    previous=None
    while True:
        try:
            state=collect_state()
            observed={k:state[k] for k in ('raw_volume','volume','state','state_source','peer_status','peer_error')}
            if observed!=previous:
                LOG.info('state %s',json.dumps(observed))
                previous=observed
            with STATE_LOCK:
                STATE_CACHE.clear();STATE_CACHE.update(state,_sampled=time.monotonic())
        except Exception as error:
            if previous!='unavailable':LOG.info('receiver unavailable %s',type(error).__name__)
            previous='unavailable'
        time.sleep(.5)

def metadata_events():
    # One non-blocking consumer of the existing Shairport metadata FIFO.
    import select
    path='/tmp/shairport-sync-metadata'
    while True:
        try:
            fd=os.open(path,os.O_RDONLY|os.O_NONBLOCK)
            try:
                buffer=b''
                while True:
                    ready,_,_=select.select([fd],[],[],1)
                    if not ready:continue
                    data=os.read(fd,65536)
                    if not data:time.sleep(.2);continue
                    buffer=(buffer+data)[-131072:]
                    while b'</item>' in buffer:
                        item,buffer=buffer.split(b'</item>',1)
                        kind=re.search(rb'<type>([0-9a-f]+)</type>',item)
                        code=re.search(rb'<code>([0-9a-f]+)</code>',item)
                        if kind and kind.group(1)==b'73736e63' and code:
                            event=bytes.fromhex(code.group(1).decode()).decode(errors='replace')
                            if event in ('paus','prsm','pbeg','pend'):
                                PLAYBACK.event_received(event)
                                LOG.info('stream event=%s',event)
            finally:os.close(fd)
        except OSError:time.sleep(2)


CONFIG_PATH = Path('/etc/shairport-sync.conf')

def renamed_config(text, value):
    if not isinstance(value, str):
        raise ValueError('Enter a receiver name.')
    name = value.strip()
    if not name or len(name.encode('utf-8')) > 50 or '%' in name or any(unicodedata.category(c).startswith('C') for c in name):
        raise ValueError('Use 1-50 UTF-8 bytes, without control characters or %.')
    # Tokenize strings and comments before locating general.name. Never replace
    # a commented example or a similarly named setting in another section.
    pattern = r'"(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\n]*|\#[^\n]*|[A-Za-z_][A-Za-z_0-9]*|[^\s]'
    tokens = [m for m in re.finditer(pattern, text, re.S)
              if not m.group().startswith(('/*', '//', '#'))]
    depth = 0
    general = False
    matches = []
    for i, token in enumerate(tokens):
        word = token.group()
        if word == '{':
            if depth == 0:
                general = i >= 2 and tokens[i-2].group() == 'general' and tokens[i-1].group() in ('=', ':')
            depth += 1
        elif word == '}':
            depth -= 1
            if depth == 0:
                general = False
        elif general and depth == 1 and word == 'name' and i+3 < len(tokens):
            assignment, val, end = tokens[i+1:i+4]
            if assignment.group() == '=' and val.group().startswith('"') and end.group() == ';':
                matches.append(val)
    if len(matches) != 1:
        raise ValueError('Expected one general.name setting. Check the receiver configuration.')
    val = matches[0]
    escaped = name.replace('\\', '\\\\').replace('"', '\\"')
    return text[:val.start()] + '"' + escaped + '"' + text[val.end():], name

def rename_receiver(value):
    with receiver_lock():
        _rename_receiver(value)

def _rename_receiver(value):
    original = CONFIG_PATH.read_text(encoding='utf-8')
    updated, name = renamed_config(original, value)
    if updated == original:
        return
    def write(content):
        tmp = CONFIG_PATH.with_suffix('.rename.tmp')
        tmp.write_text(content, encoding='utf-8')
        os.chmod(tmp, CONFIG_PATH.stat().st_mode & 0o777)
        tmp.replace(CONFIG_PATH)
    _, old_props, _ = interfaces()
    old_volume = float(old_props.Get(IFACE, 'Volume', timeout=2))
    backup = CONFIG_PATH.with_suffix('.before-rename')
    backup.write_text(original, encoding='utf-8')
    os.chmod(backup, 0o600)
    write(updated)
    try:
        restart_receiver()
        for _ in range(30):
            try:
                core, _, _ = interfaces()
                if str(core.Get('org.gnome.ShairportSync', 'ServiceName', timeout=.5)) == name:
                    _, props, _ = interfaces()
                    props.Set(IFACE, 'Volume', dbus.Double(old_volume), timeout=2)
                    return
            except Exception:
                pass
            time.sleep(.1)
        raise RuntimeError('New name was not advertised')
    except Exception:
        write(original)
        try:
            restart_receiver()
        except Exception:
            pass
        raise RuntimeError('Rename failed. Previous name restored; receiver reconnecting.')


def set_volume(value):
    value = float(value)
    if not math.isfinite(value) or not 0 <= value <= 100:
        raise ValueError('Invalid volume')
    _, props, _ = interfaces()
    props.Set(IFACE, 'Volume', dbus.Double(value / 100), timeout=3)

class PeerHandler(BaseHTTPRequestHandler):
    nonces = {}
    def setup(self):
        super().setup()
        self.connection.settimeout(5)
    def log_message(self, *_):
        pass
    def reply(self, code, data):
        payload = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        signature=hmac.new(getattr(self,'auth_secret',PAIR.get('secret','')).encode(),self.headers.get('X-Echo-Nonce','').encode()+b'\n'+payload,hashlib.sha256).hexdigest()
        self.send_header('X-Echo-Signature',signature)
        self.end_headers()
        self.wfile.write(payload)
    def do_GET(self):
        self.reply(403, {'error':'Forbidden'})
    def do_POST(self):
        if self.path.startswith('/pair/'):
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not PAIRING or not 0<length<=4096:raise ValueError('Invalid pairing request')
                data=json.loads(self.rfile.read(length))
                if self.path=='/pair/hello':result=PAIRING.hello(data,self.client_address[0])
                elif self.path=='/pair/confirm':result=PAIRING.accept(data)
                else:raise ValueError('Unknown pairing request')
                return self.reply(200,result)
            except Exception:return self.reply(400,{'error':'Pairing unavailable. Open pairing on both screens.'})
        self.auth_secret=PAIR.get('secret','')
        if not self.auth_secret:return self.reply(403,{'error':'Unpaired'})
        self.connection.settimeout(4)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if self.path != '/peer' or not 0 < length <= 1024:
                return self.reply(400, {'error':'Invalid request'})
            body = self.rfile.read(length)
            stamp = self.headers.get('X-Echo-Time', '')
            nonce = self.headers.get('X-Echo-Nonce', '')
            expected = hmac.new(PAIR['secret'].encode(), stamp.encode()+b'\n'+nonce.encode()+b'\n'+body, hashlib.sha256).hexdigest()
            now = time.time()
            if not math.isfinite(float(stamp)) or abs(now - float(stamp)) > 30 or not nonce or len(nonce) > 64 or not hmac.compare_digest(expected, self.headers.get('X-Echo-Signature', '')):
                return self.reply(403, {'error':'Forbidden'})
            self.nonces = {key:expiry for key,expiry in self.nonces.items() if expiry > now}
            if nonce in self.nonces:
                return self.reply(403, {'error':'Replay'})
            type(self).nonces = {**self.nonces, nonce:now+60}
            request = json.loads(body)
            action = request.get('action')
            applied=True
            if action in ('volume','link','sleep','sleep_cancel','unpair'):
                if 'session' not in request:
                    return self.reply(409,{'error':'Update both receivers for reliable linking','protocol':2})
                if action=='volume':
                    value=float(request['value'])
                    if not math.isfinite(value) or not 0<=value<=100:raise ValueError()
                    callback=lambda:set_volume(value)
                elif action=='link':
                    if not isinstance(request.get('enabled'),bool):raise ValueError()
                    callback=lambda:set_link(request['enabled'])
                elif action=='sleep':callback=lambda:PREFERENCES.start(deadline=request['deadline'],pause=False)
                elif action=='sleep_cancel':callback=lambda:PREFERENCES.cancel()
                else:callback=lambda:commit_pair({})
                applied=CONTROL_ORDER.apply(request,callback)
                LOG.info('peer control action=%s applied=%s value=%s',action,applied,request.get('value'))
            elif action!='state':
                return self.reply(400,{'error':'Invalid action'})
            try:
                state=read_state()
                result={key:state[key] for key in ('name','volume','active','linked')}
                result.update(ready=True)
            except Exception:
                result=dict(ready=False,linked=bool(PAIR.get('linked')))
            self.reply(200,dict(result,protocol=2,features=['sleep-v1','unpair-v1'],applied=applied))
        except (ValueError, KeyError, TypeError):
            self.reply(400, {'error':'Invalid request'})
        except Exception:
            self.reply(503, {'error':'Receiver unavailable'})

class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *_):
        pass

    def reply(self, status, data, mime='application/json; charset=utf-8'):
        if isinstance(data, (dict, list)):
            data = json.dumps(data, ensure_ascii=False).encode()
        elif isinstance(data, str):
            data = data.encode()
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.headers.get('Host') != '127.0.0.1:8765':
            return self.reply(403, {'error': 'Local access only'})
        path = urlparse(self.path).path
        try:
            if path == '/':
                return self.reply(200, (ROOT / 'index.html').read_text().replace('__TOKEN__', TOKEN), 'text/html; charset=utf-8')
            if path == '/api/session':
                return self.reply(200, {'token': TOKEN})
            if path == '/api/state':
                return self.reply(200, dict(read_state(), token=TOKEN, **feature_state()))
            if path == '/api/art':
                _, props, _ = interfaces()
                metadata = props.Get(IFACE, 'Metadata', timeout=3)
                art = artwork_path(metadata.get('mpris:artUrl', ''))
                if art:
                    return self.reply(200, art.read_bytes(), mimetypes.guess_type(str(art))[0] or 'image/jpeg')
            return self.reply(404, {'error': 'Not found'})
        except Exception:
            return self.reply(503, {'ok': False, 'error': 'Receiver connecting. Please wait.'})

    def do_POST(self):
        if self.headers.get('Host') != '127.0.0.1:8765' or self.headers.get('X-Echo-Token') != TOKEN or self.headers.get('Origin', ORIGIN) != ORIGIN:
            return self.reply(403, {'error': 'Local access only'})
        if self.path != '/api/control':
            return self.reply(404, {'error': 'Not found'})
        action = None
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 65536:
                return self.reply(400, {'error': 'Invalid request'})
            data = json.loads(self.rfile.read(length))
            action = data.get('action')
            if PREFERENCES:
                result=feature_action(data)
                if result is not None:return self.reply(200,result)
            if action == 'rename':
                rename_receiver(data.get('value'))
                return self.reply(200, {'ok': True})
            state = read_state()
            _, props, player = interfaces()
            methods = {'toggle': 'PlayPause', 'next': 'Next', 'previous': 'Previous'}
            if action == 'volume':
                value = float(data['value'])
                if not math.isfinite(value) or not 0 <= value <= 100:
                    return self.reply(400, {'error': 'Invalid volume'})
                with CONTROL_ORDER.lock:
                    set_volume(value)
                LOG.info('touch volume value=%s linked=%s',value,bool(PAIR.get('linked')))
                if PAIR.get('linked'):
                    try:
                        peer_call('volume', value=value)
                    except Exception:
                        reason='Update both receivers for reliable linking.' if HEALTH.snapshot().get('protocol',0)<2 else 'Peer reconnecting or unavailable.'
                        return self.reply(200, {'ok':True, 'warning':'Only this device changed volume. '+reason})
            elif action == 'link' and PAIR.get('secret'):
                enabled = data.get('enabled')
                if not isinstance(enabled, bool):
                    raise ValueError()
                if not enabled:
                    set_link(False)
                    try:
                        peer_call('link', enabled=False)
                    except Exception:
                        return self.reply(200, {'ok':True, 'warning':'Link disabled here. Peer offline; disable linking on that device too.'})
                    return self.reply(200, {'ok':True})
                if HEALTH.snapshot().get('protocol',0)<2:
                    return self.reply(409, {'error':'Update both receivers to use reliable volume linking.'})
                # Align to the quieter receiver when linking, avoiding a surprise increase.
                result = peer_call('link', enabled=enabled)
                set_link(enabled)
                if enabled:
                    value = min(state['volume'], result['volume'])
                    set_volume(value)
                    peer_call('volume', value=value)
            elif action in methods and state['can_' + action]:
                getattr(player, methods[action])(timeout=3)
            else:
                return self.reply(409, {'error': 'This control is unavailable. Use your iPhone.'})
            return self.reply(200, {'ok': True})
        except ValueError as error:
            return self.reply(400, {'error': str(error) or 'Invalid request'})
        except (KeyError, TypeError):
            return self.reply(400, {'error': 'Invalid request'})
        except Exception:
            return self.reply(503, {'error': 'Rename failed. Previous name restored; receiver reconnecting.' if action == 'rename' else 'Action failed. Please try again.'})

if __name__ == '__main__':
    os.umask(0o077)
    log_path=Path('/run/echo-airplay/diagnostics.log')
    log_path.parent.mkdir(parents=True,exist_ok=True)
    handler=RotatingFileHandler(log_path,maxBytes=262144,backupCount=3)
    os.chmod(log_path,0o600)
    handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
    LOG.addHandler(handler);LOG.setLevel(logging.INFO)
    PREFERENCES=Preferences(ROOT/'preferences.json',set_output,pause_sender)
    PAIRING=Pairing(ROOT/'identity.json',PAIR.get('self_service'),lambda:STATE_CACHE.get('name','Echo AirPlay'),lambda:bool(PAIR.get('secret')),commit_pair)
    threading.Thread(target=feature_worker,daemon=True).start()
    threading.Thread(target=sample_state,daemon=True).start()
    threading.Thread(target=metadata_events,daemon=True).start()
    peer_server = HTTPServer(('0.0.0.0', 8766), PeerHandler)
    threading.Thread(target=peer_server.serve_forever, daemon=True).start()
    threading.Thread(target=monitor_peer, daemon=True).start()
    HTTPServer(('127.0.0.1', 8765), Handler).serve_forever()
