import hashlib,hmac,json,unittest
from unittest.mock import Mock,patch
from urllib.error import HTTPError
from test_discovery import server
from reliability import PeerHealth

class Response:
    def __init__(self,request,valid=True,ready=True):
        self.body=json.dumps(dict(protocol=2,ready=ready,name='Peer',volume=40)).encode()
        nonce=dict((k.lower(),v) for k,v in request.header_items())['x-echo-nonce']
        signature=hmac.new(b'test-secret',nonce.encode()+b'\n'+self.body,hashlib.sha256).hexdigest()
        self.headers={'X-Echo-Signature':signature if valid else 'invalid'}
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,limit):return self.body[:limit]

class TransportTests(unittest.TestCase):
    def setUp(self):
        for p in (patch.dict(server.PAIR,dict(secret='test-secret',peer_service='peer'),clear=True),
                  patch.object(server,'HEALTH',PeerHealth()),patch.object(server,'PEER',{}),
                  patch.object(server,'peer_address',('192.0.2.1',0)),
                  patch.object(server,'system_bus',return_value=Mock())):
            p.start();self.addCleanup(p.stop)
    def test_discovery_failure_uses_authenticated_cached_address(self):
        resolver=Mock();resolver.ResolveService.side_effect=RuntimeError()
        opener=Mock();opener.open.side_effect=lambda request,timeout:Response(request)
        with patch.object(server.dbus,'Interface',return_value=resolver),patch.object(server,'build_opener',return_value=opener):
            server.peer_call('state')
        self.assertTrue(server.HEALTH.snapshot()['online'])
        self.assertIn('192.0.2.1',opener.open.call_args.args[0].full_url)
    def test_changed_address_and_receiver_not_ready_are_distinct(self):
        resolver=Mock();resolver.ResolveService.return_value=[None]*7+['192.0.2.2']
        opener=Mock();opener.open.side_effect=lambda request,timeout:Response(request,ready=False)
        with patch.object(server.dbus,'Interface',return_value=resolver),patch.object(server,'build_opener',return_value=opener):
            server.peer_call('state')
        self.assertEqual(server.peer_address[0],'192.0.2.2')
        self.assertTrue(server.HEALTH.snapshot()['online'])
        self.assertFalse(server.HEALTH.snapshot()['ready'])
    def test_bad_new_address_falls_back_without_losing_verified_address(self):
        resolver=Mock();resolver.ResolveService.return_value=[None]*7+['192.0.2.99']
        opener=Mock()
        def respond(request,timeout):
            if '192.0.2.99' in request.full_url:raise ConnectionRefusedError()
            return Response(request)
        opener.open.side_effect=respond
        with patch.object(server.dbus,'Interface',return_value=resolver),patch.object(server,'build_opener',return_value=opener):
            server.peer_call('state')
        self.assertEqual(server.peer_address[0],'192.0.2.1')
        self.assertEqual(opener.open.call_count,2)
        self.assertTrue(server.HEALTH.snapshot()['online'])

    def test_network_failure_retains_address_for_rediscovery(self):
        opener=Mock();opener.open.side_effect=ConnectionRefusedError()
        with patch.object(server,'peer_address',('192.0.2.1',server.time.monotonic())),patch.object(server,'build_opener',return_value=opener):
            with self.assertRaises(ConnectionRefusedError):server.peer_call('state')
            self.assertEqual(server.peer_address,('192.0.2.1',0))
        self.assertEqual(server.HEALTH.snapshot()['error'],'network')
    def test_bad_response_signature_and_legacy_control_are_rejected(self):
        opener=Mock();opener.open.side_effect=lambda request,timeout:Response(request,valid=False)
        with patch.object(server,'peer_address',('192.0.2.1',server.time.monotonic())),patch.object(server,'build_opener',return_value=opener):
            with self.assertRaises(PermissionError):server.peer_call('state')
            self.assertEqual(server.HEALTH.snapshot()['error'],'authentication')
            with self.assertRaisesRegex(RuntimeError,'Update both'):server.peer_call('volume',value=30)
            self.assertEqual(opener.open.call_count,1)

if __name__=='__main__':unittest.main()
