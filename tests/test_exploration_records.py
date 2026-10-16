import tempfile
import unittest
from pathlib import Path
from digitalmon.store import Store

class ExplorationTests(unittest.TestCase):
    def test_record_exposes_actual_saved_source_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'life.sqlite')
            jid=store.enqueue('research',{'url':'https://example.com/'})
            job=store.claim()
            store.complete_research(jid,{'title':'Document','text':'Actual retrieved evidence',
                'url':'https://example.com/','sha256':'abc'},job['control_epoch'])
            result=Store(Path(tmp)/'life.sqlite').explorations()[0]
            self.assertEqual(result['status'],'completed')
            self.assertIn('Actual retrieved evidence',result['memory']['text'])
            self.assertEqual(result['result']['sha256'],'abc')
