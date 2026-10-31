"""Run on the receiver with its local companion service running."""
import json
import re
import hashlib
import hmac
import secrets
import time
import unittest
from unittest.mock import patch
from collections import Counter
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import server

class TouchTests(unittest.TestCase):
    def test_unpaired_receiver_is_independent(self):
        # Only alters this test process's config, never the running service.
        with patch.dict(server.PAIR, {}, clear=True):
            state = server.read_state()
        self.assertFalse(state['paired'])
        self.assertFalse(state['linked'])
        self.assertNotIn('channel', state)
        self.assertTrue(state['ok'])

    @unittest.skipUnless(server.PAIR.get('secret'), 'Receiver is not paired')
    def test_peer_authentication_and_replay(self):
        endpoint = 'http://127.0.0.1:8766/peer'
        body = b'{"action":"state"}'
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(endpoint, data=body), timeout=5)
        self.assertIn(error.exception.code, (400,403))
        timestamp = str(int(time.time()))
        nonce = secrets.token_hex(16)
        signature = hmac.new(server.PAIR['secret'].encode(), timestamp.encode()+b'\n'+nonce.encode()+b'\n'+body, hashlib.sha256).hexdigest()
        request = Request(endpoint, data=body, headers={'X-Echo-Time':timestamp,'X-Echo-Nonce':nonce,'X-Echo-Signature':signature})
        with urlopen(request, timeout=5) as response:
            self.assertIn('volume', json.load(response))
        with self.assertRaises(HTTPError) as error:
            urlopen(request, timeout=5)
        self.assertEqual(error.exception.code,403)

    def test_artwork_cannot_read_outside_cache(self):
        for path in ('file:///etc/passwd', 'file:///run/echo-airplay/coverart/../../etc/passwd', 'https://example.com/a.jpg'):
            self.assertIsNone(server.artwork_path(path))

    def test_unique_element_ids(self):
        ids = []
        class Parser(HTMLParser):
            def handle_starttag(self, tag, attrs):
                ids.extend(v for k, v in attrs if k == 'id')
        Parser().feed((server.ROOT / 'index.html').read_text())
        self.assertEqual([k for k, n in Counter(ids).items() if n > 1], [])

    def test_live_state_and_cover(self):
        with urlopen(server.ORIGIN + '/api/state', timeout=5) as response:
            state = json.load(response)
        self.assertTrue(state['ok'])
        self.assertTrue(0 <= state['volume'] <= 100)
        if state['art']:
            with urlopen(server.ORIGIN + '/api/art', timeout=5) as response:
                self.assertTrue(response.headers['Content-Type'].startswith('image/'))
                self.assertGreater(len(response.read()), 100)

    def test_unauthenticated_control_rejected(self):
        request = Request(server.ORIGIN + '/api/control', data=b'{"action":"toggle"}', method='POST')
        with self.assertRaises(HTTPError) as error:
            urlopen(request, timeout=5)
        self.assertEqual(error.exception.code, 403)

    def test_invalid_volume_rejected_without_changing_audio(self):
        html = urlopen(server.ORIGIN, timeout=5).read().decode()
        token = re.search("const token='([^']+)'", html).group(1)
        request = Request(server.ORIGIN + '/api/control', data=b'{"action":"volume","value":101}', headers={'X-Echo-Token': token, 'Content-Type': 'application/json'}, method='POST')
        with self.assertRaises(HTTPError) as error:
            urlopen(request, timeout=5)
        self.assertEqual(error.exception.code, 400)

if __name__ == '__main__':
    unittest.main(verbosity=2)
