"""Explicit two-screen pairing using X25519 and a 48-bit comparison code."""
import re
import base64,hashlib,hmac,ipaddress,json,os,secrets,shlex,subprocess,tempfile,threading,time
from pathlib import Path
from urllib.request import Request,build_opener,ProxyHandler
from xml.sax.saxutils import escape

class Exchange:
    def __init__(self):
        self.private=subprocess.check_output(['openssl','genpkey','-algorithm','X25519'],stderr=subprocess.DEVNULL,timeout=5)
        self.public=subprocess.check_output(['openssl','pkey','-pubout','-outform','DER'],input=self.private,stderr=subprocess.DEVNULL,timeout=5)[-32:]
    def shared(self,public):
        if len(public)!=32:raise ValueError('Invalid pairing public key')
        with tempfile.TemporaryDirectory() as folder:
            private=Path(folder)/'private.pem';peer=Path(folder)/'peer.der'
            private.write_bytes(self.private);os.chmod(private,0o600)
            peer.write_bytes(bytes.fromhex('302a300506032b656e032100')+public)
            return subprocess.check_output(['openssl','pkeyutl','-derive','-inkey',str(private),'-peerkey',str(peer),'-peerform','DER'],stderr=subprocess.DEVNULL,timeout=5)

def key_for(exchange,local,remote):
    public=base64.b64decode(remote['public'],validate=True)
    shared=exchange.shared(public)
    if len(shared)!=32 or shared==bytes(32):raise ValueError('Invalid shared key')
    transcript=json.dumps(sorted([local,remote],key=lambda p:p['id']),sort_keys=True,separators=(',',':')).encode()
    salt=hashlib.sha256(b'echo-touch-pair-v1'+transcript).digest()
    prk=hmac.new(salt,shared,hashlib.sha256).digest()
    return hmac.new(prk,b'pair-key'+salt+b'\x01',hashlib.sha256).digest()

def avahi_unescape(value):
    # Parsable Avahi output escapes UTF-8 bytes as decimal backslash sequences.
    raw=value.encode('utf-8')
    return re.sub(rb'\\([0-9]{3})',lambda m:bytes([int(m[1])]) if int(m[1])<256 else m[0],raw).decode('utf-8',errors='replace')


def discover(own_id):
    try:
        result=subprocess.run(['avahi-browse','-rtp','_echo-touch._tcp'],capture_output=True,timeout=4)
        output=result.stdout
    except subprocess.TimeoutExpired as e:output=e.stdout or b''
    found={}
    for line in output.decode(errors='replace').splitlines():
        parts=[avahi_unescape(part) for part in line.split(';',9)]
        if len(parts)!=10 or parts[0]!='=' or parts[2]!='IPv4' or parts[3]==own_id or parts[8]!='8766':continue
        try:
            ipaddress.IPv4Address(parts[7])
            txt=dict(item.split('=',1) for item in shlex.split(parts[9]) if '=' in item)
            found[parts[3]]=dict(id=parts[3],name=txt.get('name',parts[3]),address=parts[7])
        except ValueError:continue
    return list(found.values())

class Pairing:
    def __init__(self,path,legacy_id,name,is_paired,commit):
        self.path=Path(path);self.name=name;self.is_paired=is_paired;self.commit=commit
        if self.path.exists():self.identity=json.loads(self.path.read_text())['id']
        else:
            self.identity=legacy_id or 'echo-touch-'+secrets.token_hex(12)
            self.path.write_text(json.dumps(dict(id=self.identity)));os.chmod(self.path,0o600)
        self.lock=threading.RLock();self.until=0;self.pending=None;self.exchange=None;self.candidates={};self.last_hello=0
    def advertise(self):
        path=Path('/etc/avahi/services/echo-touch.service');path.parent.mkdir(parents=True,exist_ok=True)
        xml='<service-group><name>'+escape(self.identity)+'</name><service><type>_echo-touch._tcp</type><port>8766</port><txt-record>name='+escape(self.name())+'</txt-record></service></service-group>'
        if not path.exists() or path.read_text()!=xml:
            tmp=path.with_suffix('.tmp');tmp.write_text(xml);os.chmod(tmp,0o644);tmp.replace(path)
    def open(self):
        with self.lock:
            if self.is_paired():raise ValueError('Remove the current pairing first.')
            self.exchange=Exchange();self.until=time.monotonic()+120;self.pending=None
            self.local=dict(id=self.identity,name=self.name(),public=base64.b64encode(self.exchange.public).decode(),nonce=secrets.token_hex(16))
    def scan(self):
        found=discover(self.identity)
        with self.lock:self.candidates={p['id']:p for p in found}
        return [dict(id=p['id'],name=p['name']) for p in found]
    def status(self):
        with self.lock:
            p=self.pending
            return dict(open=time.monotonic()<self.until,remaining=max(0,int(self.until-time.monotonic())),
                        code=p['code'] if p and time.monotonic()<self.until else '',
                        peer_name=p['remote']['name'] if p else '',confirmed=p['local_confirmed'] if p else False,
                        committed=p.get('committed',False) if p else False)
    def establish(self,remote,address):
        if not isinstance(remote,dict) or set(remote)!=set(('id','name','public','nonce')):raise ValueError('Invalid pairing offer')
        if any(not isinstance(v,str) for v in remote.values()) or len(remote['name'])>80 or not 1<=len(remote['id'])<=100 or len(remote['nonce'])!=32:raise ValueError('Invalid pairing offer')
        if remote['id']==self.identity:raise ValueError('Cannot pair with this device')
        key=key_for(self.exchange,self.local,remote)
        code=hmac.new(key,b'compare-both-screens',hashlib.sha256).hexdigest()[:12].upper()
        self.pending=dict(remote=remote,address=address,key=key,code=' '.join(code[i:i+4] for i in range(0,12,4)),local_confirmed=False,remote_confirmed=False,committed=False)
    def hello(self,remote,address):
        with self.lock:
            if time.monotonic()>=self.until or self.is_paired() or self.pending:raise ValueError('Open pairing on both screens first.')
            if time.monotonic()-self.last_hello<2:raise ValueError('Please wait before retrying.')
            self.last_hello=time.monotonic();self.establish(remote,address)
            return self.local
    def start(self,target):
        with self.lock:
            if time.monotonic()>=self.until or self.pending:raise ValueError('Open pairing again.')
            candidate=self.candidates.get(target)
            if not candidate:raise ValueError('Scan and choose a receiver first.')
            remote=self.send(candidate['address'],'hello',self.local)
            if remote.get('id')!=target:raise ValueError('Receiver identity changed; scan again.')
            self.establish(remote,candidate['address'])
    def send(self,address,action,body):
        ipaddress.IPv4Address(address)
        request=Request('http://'+address+':8766/pair/'+action,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        with build_opener(ProxyHandler({})).open(request,timeout=4) as response:
            data=response.read(4097)
            if len(data)>4096:raise ValueError('Invalid pairing response')
            return json.loads(data)
    def proof(self,confirmed):
        p=self.pending;payload=dict(id=self.identity,confirmed=confirmed)
        payload['proof']=hmac.new(p['key'],json.dumps(payload,sort_keys=True).encode(),hashlib.sha256).hexdigest()
        return payload
    def accept(self,body):
        with self.lock:
            p=self.pending
            if not p or time.monotonic()>=self.until:raise ValueError('Pairing expired.')
            if set(body)!=set(('id','confirmed','proof')) or body['id']!=p['remote']['id'] or type(body['confirmed']) is not bool:raise ValueError('Invalid confirmation')
            expected=hmac.new(p['key'],json.dumps(dict(id=body['id'],confirmed=body['confirmed']),sort_keys=True).encode(),hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected,body['proof']):raise ValueError('Pairing confirmation failed')
            p['remote_confirmed']=body['confirmed'];self.finish()
            return self.proof(p['local_confirmed'])
    def finish(self):
        p=self.pending
        if p['local_confirmed'] and p['remote_confirmed'] and not p['committed']:
            self.commit(dict(self_service=self.identity,peer_service=p['remote']['id'],peer_name=p['remote']['name'],secret=p['key'].hex(),linked=False))
            p['committed']=True
    def confirm(self,code):
        with self.lock:
            if not self.pending or code!=self.pending['code'] or time.monotonic()>=self.until:raise ValueError('Pairing code expired.')
            self.pending['local_confirmed']=True
        self.poll()
    def poll(self):
        with self.lock:
            p=self.pending
            if not p or not p['local_confirmed'] or p['committed'] or time.monotonic()>=self.until:return
            address=p['address'];body=self.proof(True)
        response=self.send(address,'confirm',body)
        self.accept(response)
