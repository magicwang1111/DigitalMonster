import tempfile
import unittest
from pathlib import Path


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def store(self):
        from digitalmon.store import Store
        return Store(Path(self.tmp.name) / 'life.sqlite')

    def test_identity_and_events_survive_restart(self):
        s = self.store()
        first = s.snapshot()
        s.tick()
        again = self.store().snapshot()
        self.assertEqual(first['id'], again['id'])
        self.assertEqual(again['ticks'], 1)
        self.assertEqual(again['events'][0]['kind'], 'action')

    def test_pause_and_invalid_control_do_not_advance(self):
        s = self.store()
        s.control('pause')
        self.assertFalse(s.tick())
        self.assertEqual(s.snapshot()['ticks'], 0)
        with self.assertRaises(ValueError):
            s.control('erase')
        s.control('resume')
        self.assertTrue(s.tick())

    def test_memory_has_source_and_search_survives_restart(self):
        s = self.store()
        message_id = s.remember('我的名字是小明')
        memories = self.store().memories('小明')
        self.assertEqual(memories[0]['id'], message_id)
        self.assertEqual(memories[0]['text'], '我的名字是小明')

    def test_world_replay_and_wall_collision(self):
        from digitalmon.world import initial, step
        a, b = initial(12), initial(12)
        for action in [0, 1, 2, 3] * 12:
            a, ra, da = step(a, action)
            b, rb, db = step(b, action)
            self.assertEqual((a, ra, da), (b, rb, db))
        s = initial(1)
        s['position'] = [0, 0]
        n, r, _ = step(s, 0)
        self.assertEqual(n['position'], [0, 0])
        self.assertLess(r, 0)


if __name__ == '__main__':
    unittest.main()
