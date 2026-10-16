import tempfile
import unittest
from pathlib import Path


class PetTests(unittest.TestCase):
    def test_interaction_persists_but_does_not_fake_learning(self):
        from digitalmon.store import Store
        from digitalmon.pet import interact, status
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp)/'life.sqlite')
            result = interact(store, 'pet')
            self.assertEqual(result['action'], 'pet')
            pet = status(Store(Path(tmp)/'life.sqlite'), tmp)
            self.assertGreater(pet['bond'], 0)
            self.assertEqual(pet['stage'], 0)
            self.assertEqual(store.snapshot()['policy_version'], 0)

    def test_evolution_requires_real_evidence_not_clicks(self):
        from digitalmon.pet import stage_for
        base = {'ticks': 1000000, 'memory_count': 5000, 'policy_version': 3, 'bond': 100}
        self.assertEqual(stage_for(base, []), 0)
        evidence = [{'size': 9, 'seed': 11, 'status': 'completed', 'test': {'success_rate': .95}},
                    {'size': 9, 'seed': 23, 'status': 'completed', 'test': {'success_rate': .96}}]
        self.assertEqual(stage_for(base, evidence), 1)
        evidence += [{'size': 21, 'seed': 31, 'status': 'completed', 'test': {'success_rate': .95}},
                     {'size': 21, 'seed': 37, 'status': 'completed', 'test': {'success_rate': .96}}]
        self.assertEqual(stage_for(base, evidence), 2)

    def test_invalid_interaction_is_rejected(self):
        from digitalmon.pet import interact
        from digitalmon.store import Store
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                interact(Store(Path(tmp)/'life.sqlite'), 'run shell')

