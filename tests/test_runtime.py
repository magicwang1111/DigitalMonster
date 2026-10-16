import tempfile
import unittest
from pathlib import Path


class RuntimeTests(unittest.TestCase):
    def test_disk_budget_rejects_new_job(self):
        from digitalmon.store import Store
        from digitalmon.runtime import Runtime
        with tempfile.TemporaryDirectory() as tmp:
            s = Store(Path(tmp)/'life.sqlite')
            r = Runtime(s, tmp, config={'max_data_bytes': 1, 'max_training_jobs_per_day': 12})
            with self.assertRaises(ValueError):
                r.queue('train', {'backend': 'cpu'})
            self.assertEqual(s.snapshot()['jobs'], [])

    def test_atomic_research_completion_rejects_cancelled_generation(self):
        from digitalmon.store import Store
        with tempfile.TemporaryDirectory() as tmp:
            s = Store(Path(tmp)/'life.sqlite')
            jid = s.enqueue('research', {'url': 'https://example.com/'})
            job = s.claim()
            s.control('pause')
            with self.assertRaises(InterruptedError):
                s.complete_research(jid, {'title': 'title', 'text': 'result', 'url': 'https://example.com/'}, job['control_epoch'])
            self.assertEqual(s.memories(), [])
            self.assertEqual(s.snapshot()['jobs'][0]['status'], 'running')

    def test_disabled_resource_cannot_accept_training(self):
        from digitalmon.store import Store
        from digitalmon.runtime import Runtime
        with tempfile.TemporaryDirectory() as tmp:
            s = Store(Path(tmp)/'life.sqlite')
            r = Runtime(s, tmp, config={'max_training_jobs_per_day': 12, 'resources': [
                {'id': 'local-4090d', 'enabled': False, 'gpu_indices': [0]}]})
            with self.assertRaises(ValueError):
                r.queue('train', {'backend': 'cpu'})

    def test_stop_resume_invalidates_old_job(self):
        from unittest.mock import patch
        from digitalmon.store import Store
        from digitalmon.runtime import Runtime
        with tempfile.TemporaryDirectory() as tmp:
            s = Store(Path(tmp)/'life.sqlite')
            s.enqueue('research', {'url': 'https://example.com/'})
            def fetch(_):
                s.control('stop')
                s.control('resume')
                return {'title': 'stale', 'text': 'must not persist', 'url': 'https://example.com/'}
            with patch('digitalmon.runtime.fetch_public', fetch):
                Runtime(s, tmp).work_once()
            self.assertEqual(s.snapshot()['memory_count'], 0)
            self.assertEqual(s.snapshot()['jobs'][0]['status'], 'cancelled')

    def test_stale_epoch_is_rejected_inside_memory_transaction(self):
        from digitalmon.store import Store
        with tempfile.TemporaryDirectory() as tmp:
            s = Store(Path(tmp)/'life.sqlite')
            epoch = s.snapshot().get('control_epoch', 0)
            s.control('pause')
            with self.assertRaises(InterruptedError):
                s.remember('stale', expected_epoch=epoch)
            self.assertEqual(s.memories(), [])

    def test_stop_reaches_external_gpu_experiments(self):
        import json
        from digitalmon.store import Store
        from digitalmon.runtime import Runtime
        with tempfile.TemporaryDirectory() as tmp:
            s = Store(Path(tmp) / 'life.sqlite')
            folder = Path(tmp)/'research'/'active-run'
            folder.mkdir(parents=True)
            (folder/'progress.json').write_text(json.dumps({'status': 'training'}))
            r = Runtime(s, Path(tmp))
            r.control('stop')
            self.assertTrue((folder/'STOP').exists())
            self.assertFalse(s.tick())

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

