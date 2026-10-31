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

def peer_call(action, **values):
    global peer_address
    if not PAIR.get('secret'):
        raise RuntimeError('Unpaired')
    if time.monotonic() - peer_address[1] > 30:
        avahi = dbus.Interface(system_bus().get_object('org.freedesktop.Avahi', '/'), 'org.freedesktop.Avahi.Server')
        result = avahi.ResolveService(-1, 0, PAIR['peer_service'], '_echo-volume._tcp', 'local', 0, 0, timeout=3)
        peer_address = (str(result[7]), time.monotonic())
    data = json.dumps(dict(action=action, **values), separators=(',', ':')).encode()
    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(16)
    signature = hmac.new(PAIR['secret'].encode(), timestamp.encode()+b'\n'+nonce.encode()+b'\n'+data, hashlib.sha256).hexdigest()
    req = Request('http://' + peer_address[0] + ':8766/peer', data=data, headers={'Content-Type':'application/json', 'X-Echo-Time':timestamp, 'X-Echo-Nonce':nonce, 'X-Echo-Signature':signature})
    try:
        with build_opener(ProxyHandler({})).open(req, timeout=3) as response:
            result = json.load(response)
        PEER.update(result, online=True)
        return result
    except Exception:
        peer_address = ('', 0)
        PEER['online'] = False
        raise

def monitor_peer():
    group = None
    while True:
        try:
            group = maintain_pair_service(group)
        except Exception:
            group = None
        try:
            peer_call('state')
        except Exception:
            PEER['online'] = False
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

def read_state():
    core, props, _ = interfaces()
    c = core.GetAll('org.gnome.ShairportSync', timeout=3)
    p = props.GetAll(IFACE, timeout=3)
    m = p.get('Metadata', {})
    active = bool(c.get('Active', False))
    art = artwork_path(m.get('mpris:artUrl', '')) if active else None
    volume = max(0, min(100, round(float(p.get('Volume', 0)) * 100)))
    duration = max(0, float(m.get('mpris:length', 0)) / 1e6)
    position = max(0, float(p.get('Position', 0)) / 1e6)
    return dict(ok=True, name=str(c.get('ServiceName', 'Echo AirPlay')), active=active,
        state=str(p.get('PlaybackStatus', 'Stopped')) if active else 'Stopped',
        title=str(m.get('xesam:title', '')) if active else '',
        artist=' · '.join(map(str, m.get('xesam:artist', []))) if active else '',
        album=str(m.get('xesam:album', '')) if active else '',
        duration=duration if active else 0, position=min(position, duration) if duration else position,
        volume=volume, art=hashlib.sha256(str(art).encode()).hexdigest()[:20] if art else '',
        can_toggle=active and bool(p.get('CanControl')) and bool(p.get('CanPause') if p.get('PlaybackStatus') == 'Playing' else p.get('CanPlay')),
        can_next=active and bool(p.get('CanGoNext')), can_previous=active and bool(p.get('CanGoPrevious')),
        paired=bool(PAIR.get('secret')), linked=bool(PAIR.get('linked')),
        peer_online=bool(PEER.get('online')), peer_volume=PEER.get('volume'), peer_name=PAIR.get('peer_name', ''))

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
        self.end_headers()
        self.wfile.write(payload)
    def do_GET(self):
        self.reply(403, {'error':'Forbidden'})
    def do_POST(self):
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
            if abs(now - float(stamp)) > 30 or not nonce or len(nonce) > 64 or not hmac.compare_digest(expected, self.headers.get('X-Echo-Signature', '')):
                return self.reply(403, {'error':'Forbidden'})
            self.nonces = {key:expiry for key,expiry in self.nonces.items() if expiry > now}
            if nonce in self.nonces:
                return self.reply(403, {'error':'Replay'})
            type(self).nonces = {**self.nonces, nonce:now+60}
            request = json.loads(body)
            action = request.get('action')
            if action == 'volume':
                set_volume(request['value'])
            elif action == 'link':
                if not isinstance(request.get('enabled'), bool):
                    raise ValueError()
                set_link(request['enabled'])
            elif action != 'state':
                return self.reply(400, {'error':'Invalid action'})
            state = read_state()
            self.reply(200, {key:state[key] for key in ('name','volume','active','linked')})
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
                return self.reply(200, dict(read_state(), token=TOKEN))
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
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 1024:
                return self.reply(400, {'error': 'Invalid request'})
            data = json.loads(self.rfile.read(length))
            action = data.get('action')
            state = read_state()
            _, props, player = interfaces()
            methods = {'toggle': 'PlayPause', 'next': 'Next', 'previous': 'Previous'}
            if action == 'volume':
                value = float(data['value'])
                if not math.isfinite(value) or not 0 <= value <= 100:
                    return self.reply(400, {'error': 'Invalid volume'})
                set_volume(value)
                if PAIR.get('linked'):
                    try:
                        peer_call('volume', value=value)
                    except Exception:
                        return self.reply(200, {'ok':True, 'warning':'Only this device changed volume. Peer offline; check its power and Wi-Fi.'})
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
        except (ValueError, KeyError, TypeError):
            return self.reply(400, {'error': 'Invalid request'})
        except Exception:
            return self.reply(503, {'error': 'Action failed. Please try again.'})

if __name__ == '__main__':
    if PAIR.get('secret'):
        peer_server = HTTPServer(('0.0.0.0', 8766), PeerHandler)
        threading.Thread(target=peer_server.serve_forever, daemon=True).start()
        threading.Thread(target=monitor_peer, daemon=True).start()
    HTTPServer(('127.0.0.1', 8765), Handler).serve_forever()
