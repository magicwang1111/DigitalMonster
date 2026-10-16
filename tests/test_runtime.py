import tempfile
import unittest
from pathlib import Path


class RuntimeTests(unittest.TestCase):
    def test_paused_runtime_does_not_claim_jobs(self):
        from digitalmon.store import Store
        from digitalmon.runtime import Runtime
        with tempfile.TemporaryDirectory() as tmp:
            s = Store(Path(tmp) / 'life.sqlite')
            s.enqueue('train', {'backend': 'cpu'})
            s.control('pause')
            r = Runtime(s, Path(tmp))
            self.assertFalse(r.work_once())
            self.assertEqual(s.snapshot()['jobs'][0]['status'], 'queued')

    def test_training_job_records_evidence_and_adopts_policy(self):
        from digitalmon.store import Store
        from digitalmon.runtime import Runtime
        with tempfile.TemporaryDirectory() as tmp:
            s = Store(Path(tmp) / 'life.sqlite')
            s.enqueue('train', {'backend': 'cpu', 'episodes': 4000})
            Runtime(s, Path(tmp)).work_once()
            state = s.snapshot()
            self.assertEqual(state['jobs'][0]['status'], 'completed')
            self.assertGreater(state['policy_version'], 0)
            self.assertGreater(state['jobs'][0]['result']['training']['updates'], 100)

    def test_crashed_jobs_are_not_automatically_resubmitted(self):
        from digitalmon.store import Store
        with tempfile.TemporaryDirectory() as tmp:
            s = Store(Path(tmp) / 'life.sqlite')
            s.enqueue('train', {})
            self.assertIsNotNone(s.claim())
            s.recover()
            self.assertIsNone(s.claim())
            self.assertEqual(s.snapshot()['jobs'][0]['status'], 'interrupted')

