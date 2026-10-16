import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from .learning import train, evaluate, compare, validate
from .network import fetch_public


class Runtime:
    def __init__(self, store, data, gpu=False, config=None):
        self.store, self.data, self.gpu = store, Path(data), gpu
        self.config = config or {'max_network_jobs_per_day': 24, 'max_training_jobs_per_day': 12,
                                 'autonomous_interval_seconds': 3600}
        self.shutdown = threading.Event()
        self.active_epoch = None

    def control(self, action):
        self.store.control(action)
        if action in ('pause', 'stop'):
            for progress in (self.data/'research').glob('*/progress.json'):
                try:
                    status = json.loads(progress.read_text(encoding='utf-8')).get('status')
                    if status in ('training', 'generating-data'):
                        (progress.parent/'STOP').touch()
                except (OSError, ValueError):
                    continue

    def resource(self):
        resources = self.config.get('resources')
        if resources is None:
            return {'enabled': True, 'gpu_indices': [0]}
        resource_id = 'local-4090d' if os.name == 'nt' else 'remote-5090'
        return next((r for r in resources if r['id'] == resource_id), {'enabled': False})

    def check_capacity(self):
        resource = self.resource()
        if not resource.get('enabled'):
            raise ValueError('host resource is disabled')
        if resource.get('root') and not self.data.resolve().is_relative_to(Path(resource['root']).resolve()):
            raise ValueError('data directory is outside the authorized resource root')
        self.data.mkdir(parents=True, exist_ok=True)
        used = sum(p.stat().st_size for p in self.data.rglob('*') if p.is_file())
        if used >= self.config.get('max_data_bytes', 2*1024**3) or shutil.disk_usage(self.data).free < 256*1024**2:
            raise ValueError('storage budget exhausted')

    def cancelled(self):
        s = self.store.snapshot()
        return (self.shutdown.is_set() or s['paused'] or s['stopped'] or
                self.active_epoch is not None and s.get('control_epoch', 0) != self.active_epoch)

    def within_budget(self, kind):
        key = 'max_network_jobs_per_day' if kind == 'research' else 'max_training_jobs_per_day'
        with self.store.db() as c:
            count = c.execute('SELECT COUNT(*) FROM jobs WHERE kind=? AND created>?',
                              (kind, time.time()-86400)).fetchone()[0]
        return count < self.config[key]

    def queue(self, kind, payload):
        self.check_capacity()
        if not self.within_budget(kind):
            raise ValueError('daily capability budget exhausted')
        if kind == 'research':
            from .network import resolve_public
            resolve_public(payload.get('url', ''))
        elif kind == 'train':
            backend = payload.get('backend', 'gpu' if self.gpu else 'cpu')
            if backend not in ('cpu', 'gpu') or backend == 'gpu' and not self.gpu:
                raise ValueError('requested backend unavailable')
            indices = self.resource().get('gpu_indices', [])
            if backend == 'gpu' and not indices:
                raise ValueError('no GPU authorized')
            payload = {'backend': backend, 'episodes': 4000, 'seed': int(payload.get('seed', 7)),
                       'device': f'cuda:{indices[0]}' if indices else None}
        return self.store.enqueue(kind, payload)

    def schedule(self):
        if self.cancelled():
            return
        with self.store.db() as c:
            latest = c.execute('SELECT MAX(created) FROM jobs').fetchone()[0] or 0
            pending = c.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0]
            research_count = c.execute("SELECT COUNT(*) FROM jobs WHERE kind='research'").fetchone()[0]
        if not pending and time.time()-latest >= self.config['autonomous_interval_seconds']:
            if self.within_budget('train'):
                self.queue('train', {'seed': 7 + self.store.snapshot()['episode']})
            urls = ['https://docs.python.org/3/library/random.html',
                    'https://docs.python.org/3/library/sqlite3.html',
                    'https://www.gutenberg.org/ebooks/11']
            if self.within_budget('research'):
                self.queue('research', {'url': urls[research_count % len(urls)],
                                       'reason': 'scheduled source-reading curriculum; rule selected'})

    def accept_policy(self, policy, training):
        validate(policy)
        result = compare(evaluate(policy), evaluate(self.store.active_policy()))
        result['training'] = training
        result['version'] = self.store.promote(policy, result, expected_epoch=self.active_epoch) if result['accepted'] else None
        return result

    def work_once(self):
        job = self.store.claim()
        if not job:
            return False
        self.active_epoch = job['control_epoch']
        try:
            self.check_capacity()
            if job['kind'] == 'research':
                result = fetch_public(job['payload']['url'])
                if self.cancelled():
                    raise InterruptedError('paused before storing network result')
                self.store.complete_research(job['id'], result, self.active_epoch)
                return True
            else:
                if job['payload'].get('backend') == 'gpu':
                    folder = self.data / 'experiments' / f'job-{job["id"]}'
                    folder.mkdir(parents=True, exist_ok=True)
                    log = folder / 'train.log'
                    with log.open('w', encoding='utf-8') as out:
                        child = subprocess.Popen([sys.executable, '-m', 'digitalmon.gpu_train', '--output',
                            str(folder), '--seed', str(job['payload'].get('seed', 7)), '--device',
                            job['payload'].get('device', 'cuda:0')], stdout=out, stderr=out)
                        start = time.monotonic()
                        while child.poll() is None:
                            if self.cancelled() or time.monotonic()-start > 180:
                                child.terminate()
                                try:
                                    child.wait(timeout=10)
                                except subprocess.TimeoutExpired:
                                    child.kill()
                                    child.wait()
                                raise InterruptedError('GPU job cancelled or budget exceeded')
                            self.shutdown.wait(0.25)
                    if child.returncode:
                        raise RuntimeError(f'GPU worker failed; see {log.name}')
                    policy = json.loads((folder / 'policy.json').read_text(encoding='utf-8'))
                    training = json.loads((folder / 'metrics.json').read_text(encoding='utf-8'))
                else:
                    policy, training = train(seed=job['payload'].get('seed', 7),
                                             episodes=job['payload'].get('episodes', 4000), cancelled=self.cancelled)
                if self.cancelled():
                    raise InterruptedError('paused before policy adoption')
                result = self.accept_policy(policy, training)
            self.store.finish(job['id'], result)
        except InterruptedError as exc:
            self.store.finish(job['id'], {'error': str(exc)}, 'cancelled')
        except Exception as exc:
            self.store.finish(job['id'], {'error': str(exc)[:500]}, 'failed')
        finally:
            self.active_epoch = None
        return True

    def activity_loop(self):
        while not self.shutdown.is_set():
            try:
                self.store.tick()
            except Exception as exc:
                print(f'activity error: {exc}', file=sys.stderr, flush=True)
            self.shutdown.wait(0.5)

    def work_loop(self):
        while not self.shutdown.is_set():
            try:
                self.schedule()
                self.work_once()
            except Exception as exc:
                print(f'worker error: {exc}', file=sys.stderr, flush=True)
            self.shutdown.wait(1)
