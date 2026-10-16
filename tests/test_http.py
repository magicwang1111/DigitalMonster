import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path


class HttpTests(unittest.TestCase):
    def setUp(self):
        from digitalmon.store import Store
        from digitalmon.runtime import Runtime
        from digitalmon.server import make_server
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / 'life.sqlite')
        self.runtime = Runtime(self.store, self.tmp.name)
        self.server = make_server(self.runtime, 'test-token', port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def post(self, route, data, token='test-token', origin=None):
        headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer '+token}
        if origin:
            headers['Origin'] = origin
        req = urllib.request.Request(self.base+route, json.dumps(data).encode(), headers)
        return json.load(urllib.request.urlopen(req))

    def test_mutations_require_auth_and_same_origin(self):
        for token, origin in [('bad', None), ('test-token', 'https://evil.example')]:
            with self.assertRaises(urllib.error.HTTPError) as err:
                self.post('/api/control', {'action': 'pause'}, token, origin)
            self.assertEqual(err.exception.code, 403)
        self.assertFalse(self.store.snapshot()['paused'])

    def test_controls_and_memory_end_to_end(self):
        self.post('/api/control', {'action': 'pause'})
        self.assertTrue(self.store.snapshot()['paused'])
        self.post('/api/message', {'text': '我叫小明'})
        self.assertIn('小明', self.store.memories()[0]['text'])
        with self.assertRaises(urllib.error.HTTPError) as err:
            self.post('/api/control', {'action': 'destroy'})
        self.assertEqual(err.exception.code, 400)

    def test_private_state_requires_auth(self):
        with self.assertRaises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(self.base+'/api/state')
        self.assertEqual(err.exception.code, 403)

