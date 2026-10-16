import tempfile
import unittest
from pathlib import Path

class BrainTests(unittest.TestCase):
    def test_one_brain_persists_and_care_updates_its_weights(self):
        from digitalmon.store import Store
        from digitalmon.brain import tick, feedback
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'life.sqlite')
            tick(store)
            before=store.snapshot()['brain']
            feedback(store,'feed')
            after=Store(Path(tmp)/'life.sqlite').snapshot()['brain']
            self.assertEqual(before['id'],after['id'])
            self.assertNotEqual(before['weights'],after['weights'])
            self.assertEqual(after['updates'],1)

    def test_pause_stops_brain_steps(self):
        from digitalmon.store import Store
        from digitalmon.brain import tick
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'life.sqlite')
            store.control('pause')
            self.assertFalse(tick(store))
