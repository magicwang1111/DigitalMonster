import unittest
from digitalmon.curriculum import clean_up_tasks,next_task

class UpstreamTests(unittest.TestCase):
    def test_normal_activity_updates_persisted_weights(self):
        import tempfile
        from pathlib import Path
        from digitalmon.store import Store
        from digitalmon.brain import tick
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'life.sqlite'
            store=Store(path)
            for _ in range(128):tick(store)
            brain=Store(path).snapshot()['brain']
            self.assertGreater(brain['updates'],0)
            self.assertTrue(any(v!=0 for row in brain['weights'] for v in row))
    def test_voyager_cleanup_keeps_order_and_removes_resolved_failures(self):
        self.assertEqual(clean_up_tasks(['a','b','a'],['a','c','a']),(['a','b'],['c']))
        first=next_task({})
        self.assertNotEqual(next_task({'completed_tasks':[first]}),first)

    def test_dosidicus_correlation_changes_real_weight(self):
        from digitalmon.vendor.dosidicus.plasticity import PlasticityEngine,PlasticityConfig
        engine=PlasticityEngine(PlasticityConfig(stdp_enabled=False))
        weights={('drive','motor'):0.0}
        for i in range(64):engine.observe({'drive':float(i%2)*100,'motor':float(i%2)*100})
        result=engine.commit(weights,['drive','motor'],externally_driven=['drive'])
        self.assertTrue(result['weight_updates'])
