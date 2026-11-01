import hashlib,hmac,json,secrets,threading,time,unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from unittest.mock import patch
from http.server import HTTPServer
from test_discovery import server
from reliability import OrderedControls

class ProtocolTests(unittest.TestCase):
    def setUp(self):
        for item in (patch.dict(server.PAIR,dict(secret='test-key',linked=True),clear=True),
                     patch.object(server,'CONTROL_ORDER',OrderedControls()),
                     patch.object(server.PeerHandler,'nonces',{})):
            item.start();self.addCleanup(item.stop)
        self.http=HTTPServer(('127.0.0.1',0),server.PeerHandler)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.http.server_close);self.addCleanup(self.http.shutdown)
    def call(self,body):
        data=json.dumps(body).encode();nonce=secrets.token_hex(16);stamp=str(int(time.time()))
        sig=hmac.new(b'test-key',stamp.encode()+b'\n'+nonce.encode()+b'\n'+data,hashlib.sha256).hexdigest()
        request=Request('http://127.0.0.1:'+str(self.http.server_port)+'/peer',data=data,headers={'X-Echo-Time':stamp,'X-Echo-Nonce':nonce,'X-Echo-Signature':sig})
        with urlopen(request,timeout=3) as response:
            payload=response.read()
            expected=hmac.new(b'test-key',nonce.encode()+b'\n'+payload,hashlib.sha256).hexdigest()
            self.assertEqual(response.headers['X-Echo-Signature'],expected)
            return json.loads(payload)
    def test_receiver_restart_is_not_network_offline(self):
        with patch.object(server,'read_state',side_effect=RuntimeError()):
            result=self.call(dict(action='state'))
        self.assertEqual(result['protocol'],2);self.assertFalse(result['ready'])
    def test_retries_and_out_of_order_requests_do_not_apply_twice(self):
        state=dict(name='Echo',volume=25,active=True,linked=True)
        with patch.object(server,'read_state',return_value=state),patch.object(server,'set_volume') as change:
            op=dict(action='volume',session='c'*32,seq=2,issued=time.time(),value=25)
            self.assertTrue(self.call(op)['applied'])
            self.assertFalse(self.call(op)['applied'])
            op['seq']=1;op['value']=50
            self.assertFalse(self.call(op)['applied'])
            change.assert_called_once_with(25.)
            op['seq']=3;op['issued']=time.time()-10
            with self.assertRaises(HTTPError) as error:self.call(op)
            self.assertEqual(error.exception.code,400)
            error.exception.close()
            change.assert_called_once()
    def test_old_state_supported_old_control_explained(self):
        with patch.object(server,'read_state',return_value=dict(name='Echo',volume=25,active=True,linked=True)):
            self.assertTrue(self.call(dict(action='state'))['ready'])
            with self.assertRaises(HTTPError) as error:self.call(dict(action='volume',value=25))
            self.assertEqual(error.exception.code,409)
            self.assertIn('Update both',error.exception.read().decode())
            error.exception.close()

if __name__=='__main__':unittest.main()
