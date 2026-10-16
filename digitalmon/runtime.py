import json
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

    def cancelled(self):
        s = self.store.snapshot()
        return self.shutdown.is_set() or s['paused'] or s['stopped']

    def within_budget(self, kind):
        key = 'max_network_jobs_per_day' if kind == 'research' else 'max_training_jobs_per_day'
        with self.store.db() as c:
            count = c.execute('SELECT COUNT(*) FROM jobs WHERE kind=? AND created>?',
                              (kind, time.time()-86400)).fetchone()[0]
        return count < self.config[key]

    def queue(self, kind, payload):
        if not self.within_budget(kind):
            raise ValueError('daily capability budget exhausted')
        if kind == 'research':
            from .network import resolve_public
            resolve_public(payload.get('url', ''))
        elif kind == 'train':
            backend = payload.get('backend', 'gpu' if self.gpu else 'cpu')
            if backend not in ('cpu', 'gpu') or backend == 'gpu' and not self.gpu:
                raise ValueError('requested backend unavailable')
            payload = {'backend': backend, 'episodes': 4000, 'seed': int(payload.get('seed', 7))}
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
        result['version'] = self.store.promote(policy, result) if result['accepted'] else None
        return result

    def work_once(self):
        job = self.store.claim()
        if not job:
            return False
        try:
            if job['kind'] == 'research':
                result = fetch_public(job['payload']['url'])
                if self.cancelled():
                    raise InterruptedError('paused before storing network result')
                result['memory_id'] = self.store.remember(result['title'] + '\n' + result['text'], result['url'])
                result = {k: v for k, v in result.items() if k not in ('text', 'links')}
            else:
                if job['payload'].get('backend') == 'gpu':
                    folder = self.data / 'experiments' / f'job-{job["id"]}'
                    folder.mkdir(parents=True, exist_ok=True)
                    log = folder / 'train.log'
                    with log.open('w', encoding='utf-8') as out:
                        child = subprocess.Popen([sys.executable, '-m', 'digitalmon.gpu_train', '--output',
                            str(folder), '--seed', str(job['payload'].get('seed', 7))], stdout=out, stderr=out)
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
