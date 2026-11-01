import json,os,shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from preferences import Preferences,validated
from pairing import Pairing,Exchange,key_for

class PreferenceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.now=[1000.];self.gain=Mock();self.pause=Mock()
  self.p=Preferences(Path(self.tmp.name)/'preferences.json',self.gain,self.pause,lambda:self.now[0])
 def test_limit_timer_fade_pause_and_cancel(self):
  self.p.update({'volume_limit':60});self.p.start(minutes=1)
  self.p.tick();self.assertEqual(self.p.applied,60)
  self.now[0]+=30;self.p.tick();self.assertEqual(self.p.applied,30)
  self.now[0]+=30;self.p.tick();self.assertEqual(self.p.applied,0);self.pause.assert_called_once()
  self.p.tick();self.pause.assert_called_once()
  self.p.cancel();self.assertEqual(self.p.applied,60);self.assertIsNone(self.p.timer)
 def test_partner_timer_does_not_pause_sender_twice(self):
  self.p.start(deadline=1060,pause=False);self.now[0]=1060;self.p.tick()
  self.assertEqual(self.p.applied,0);self.pause.assert_not_called()
 def test_restart_keeps_limit_and_expired_timer_muted(self):
  self.p.update({'volume_limit':35,'layout':'large-text'});self.p.start(minutes=1)
  self.now[0]=1070
  restored=Preferences(self.p.path,self.gain,self.pause,lambda:self.now[0]);restored.tick()
  self.assertEqual(restored.settings['volume_limit'],35);self.assertEqual(restored.applied,0)
 def test_audio_failure_does_not_save_new_limit(self):
  self.gain.side_effect=RuntimeError()
  with self.assertRaises(RuntimeError):self.p.update({'volume_limit':80})
  self.assertEqual(self.p.settings['volume_limit'],100)
 def test_pause_failure_stays_visible_and_muted(self):
  self.pause.side_effect=RuntimeError();self.p.start(minutes=1);self.now[0]+=60
  self.p.tick();self.p.tick();self.assertTrue(self.p.error);self.assertEqual(self.p.applied,0)
 def test_validation(self):
  for values in ({'volume_limit':101},{'volume_limit':True},{'night_start':24},{'layout':'other'},{'idle_clock':1},{'secret':'no'}):
   with self.assertRaises(ValueError):validated(values)
  for minutes in (0,181,True,'30'):
   with self.assertRaises(ValueError):self.p.start(minutes=minutes)

class DiscoveryParsingTests(unittest.TestCase):
 def test_escaped_identity_excludes_self_and_preserves_peer_identity(self):
  from pairing import discover,avahi_unescape
  output=(r'=;wlan0;IPv4;Echo\032Volume\032ONE;_echo-touch._tcp;local;one.local;192.0.2.1;8766;"name=One"'+'\n'+
          r'=;wlan0;IPv4;Echo\032Volume\032TWO;_echo-touch._tcp;local;two.local;192.0.2.2;8766;"name=Two"').encode()
  with patch('pairing.subprocess.run',return_value=Mock(stdout=output)):
   self.assertEqual(discover('Echo Volume ONE'),[dict(id='Echo Volume TWO',name='Two',address='192.0.2.2')])
  self.assertEqual(avahi_unescape(r'caf\195\169'),'caf'+'\u00e9')

@unittest.skipUnless(shutil.which('openssl'),'OpenSSL integration runs on receiver')
class PairingTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.ac=Mock();self.bc=Mock()
  self.a=Pairing(Path(self.tmp.name)/'a.json','a-id',lambda:'Living Room',lambda:False,self.ac)
  self.b=Pairing(Path(self.tmp.name)/'b.json','b-id',lambda:'Bedroom',lambda:False,self.bc)
 def establish(self):
  self.a.open();self.b.open()
  offer=self.b.hello(self.a.local,'192.0.2.1');self.a.establish(offer,'192.0.2.2')
 def test_real_x25519_matching_code_and_two_confirmations(self):
  self.establish();self.assertEqual(self.a.status()['code'],self.b.status()['code'])
  self.assertEqual(len(self.a.status()['code'].replace(' ','')),12)
  self.ac.assert_not_called();self.bc.assert_not_called()
  self.a.pending['local_confirmed']=True
  answer=self.b.accept(self.a.proof(True));self.a.accept(answer)
  self.ac.assert_not_called();self.bc.assert_not_called()
  self.b.pending['local_confirmed']=True
  answer=self.a.accept(self.b.proof(True));self.b.accept(answer)
  self.ac.assert_called_once();self.bc.assert_called_once()
  self.assertEqual(self.ac.call_args.args[0]['secret'],self.bc.call_args.args[0]['secret'])
  self.assertFalse(self.ac.call_args.args[0]['linked'])
 def test_closed_window_wrong_confirmation_and_expiry(self):
  with self.assertRaises(ValueError):self.a.hello({},'192.0.2.2')
  self.establish();bad=self.a.proof(True);bad['proof']='0'*64
  with self.assertRaises(ValueError):self.b.accept(bad)
  self.a.until=0
  with self.assertRaises(ValueError):self.a.confirm(self.a.pending['code'])
  self.ac.assert_not_called()
 def test_zero_public_key_rejected(self):
  import base64
  self.a.open();self.b.open();bad=dict(self.b.local,public=base64.b64encode(bytes(32)).decode())
  with self.assertRaises(Exception):self.a.establish(bad,'192.0.2.2')
  self.assertIsNone(self.a.pending)

if __name__=='__main__':unittest.main()
