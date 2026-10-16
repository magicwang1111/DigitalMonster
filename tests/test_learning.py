import tempfile
import unittest
from pathlib import Path


class LearningTests(unittest.TestCase):
    def test_training_improves_on_held_out_episode_seeds(self):
        from digitalmon.learning import train, evaluate, compare
        policy, meta = train(seed=7, episodes=4000)
        self.assertGreater(meta['updates'], 100)
        self.assertTrue(any(any(v != 0 for v in row) for row in policy.values()))
        baseline = evaluate({}, range(100000, 100050))
        candidate = evaluate(policy, range(100000, 100050))
        self.assertGreater(candidate['success_rate'], 0.85)
        self.assertTrue(compare(candidate, baseline)['accepted'])

    def test_regression_and_equal_policy_are_rejected(self):
        from digitalmon.learning import compare
        self.assertFalse(compare({'mean_reward': 5, 'success_rate': 0.8},
                                 {'mean_reward': 8, 'success_rate': 1})['accepted'])
        self.assertFalse(compare({'mean_reward': 8, 'success_rate': 1},
                                 {'mean_reward': 8, 'success_rate': 1})['accepted'])

    def test_corrupt_policy_does_not_replace_active_version(self):
        from digitalmon.store import Store
        with tempfile.TemporaryDirectory() as tmp:
            s = Store(Path(tmp) / 'life.sqlite')
            with self.assertRaises(ValueError):
                s.promote({'0,0,2,2': [float('nan')] * 4}, {})
            self.assertEqual(s.snapshot()['policy_version'], 0)

    def test_policy_rollback_and_pause_guard(self):
        from digitalmon.store import Store
        with tempfile.TemporaryDirectory() as tmp:
            s = Store(Path(tmp) / 'life.sqlite')
            v = s.promote({'0,0,2,2': [1, 2, 3, 4]}, {'source': 'test'})
            self.assertEqual(s.snapshot()['policy_version'], v)
            s.rollback(0)
            self.assertEqual(s.active_policy(), {})
            s.control('pause')
            self.assertIsNone(s.promote({'0,0,2,2': [1, 2, 3, 4]}, {}))

