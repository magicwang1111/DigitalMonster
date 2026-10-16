import json
import random
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from .world import initial, key, step, WALLS, SIZE


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as c:
            c.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS life (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, ts REAL, kind TEXT, data TEXT);
                CREATE TABLE IF NOT EXISTS memories (id INTEGER PRIMARY KEY, ts REAL, text TEXT, source TEXT);
                CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY, created REAL, updated REAL,
                    kind TEXT, status TEXT, payload TEXT, result TEXT);
                CREATE TABLE IF NOT EXISTS policies (id INTEGER PRIMARY KEY, ts REAL, policy TEXT, metrics TEXT);
            ''')
            state = {'id': str(uuid.uuid4()), 'name': '初生', 'born': time.time(), 'ticks': 0,
                     'paused': False, 'stopped': False, 'episode': 0, 'world': initial(0),
                     'policy_version': 0, 'total_reward': 0.0, 'resources_collected': 0}
            c.execute('INSERT OR IGNORE INTO life VALUES(1,?)', (json.dumps(state),))

    @contextmanager
    def db(self):
        c = sqlite3.connect(self.path, timeout=15)
        c.row_factory = sqlite3.Row
        try:
            with c:
                yield c
        finally:
            c.close()

    @staticmethod
    def _state(c):
        return json.loads(c.execute('SELECT value FROM life WHERE id=1').fetchone()[0])

    @staticmethod
    def _save(c, state):
        c.execute('UPDATE life SET value=? WHERE id=1', (json.dumps(state),))

    @staticmethod
    def _event(c, kind, data):
        c.execute('INSERT INTO events(ts,kind,data) VALUES(?,?,?)',
                  (time.time(), kind, json.dumps(data, ensure_ascii=False)))
        c.execute('DELETE FROM events WHERE id <= (SELECT MAX(id)-10000 FROM events)')

    def event(self, kind, data):
        with self.db() as c:
            self._event(c, kind, data)

    def snapshot(self):
        with self.db() as c:
            s = self._state(c)
            s['events'] = [{**dict(r), 'data': json.loads(r['data'])} for r in
                           c.execute('SELECT * FROM events ORDER BY id DESC LIMIT 40')]
            s['jobs'] = [{**dict(r), 'payload': json.loads(r['payload']),
                          'result': json.loads(r['result']) if r['result'] else None} for r in
                         c.execute('SELECT * FROM jobs ORDER BY id DESC LIMIT 30')]
            s['policies'] = [{'id': r['id'], 'ts': r['ts'], 'metrics': json.loads(r['metrics'])}
                             for r in c.execute('SELECT * FROM policies ORDER BY id DESC LIMIT 10')]
            s['terrain'] = {'size': SIZE, 'walls': sorted(WALLS)}
            s['memory_count'] = c.execute('SELECT COUNT(*) FROM memories').fetchone()[0]
            return s

    def tick(self):
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            s = self._state(c)
            if s['paused'] or s['stopped']:
                return False
            world = s['world']
            if world['energy'] <= 0 or world['collected']:
                s['episode'] += 1
                world = initial(s['episode'])
            row = c.execute('SELECT policy FROM policies WHERE id=?', (s['policy_version'],)).fetchone()
            policy = json.loads(row[0]) if row else {}
            values = policy.get(key(world))
            action = max(range(4), key=lambda a: values[a]) if values else random.Random(s['ticks']).randrange(4)
            s['world'], reward, done = step(world, action)
            s['ticks'] += 1
            s['total_reward'] = round(s['total_reward'] + reward, 3)
            s['resources_collected'] += int(s['world']['collected'])
            self._save(c, s)
            self._event(c, 'action', {'action': action, 'reward': reward, 'done': done,
                                     'tick': s['ticks'], 'policy_version': s['policy_version']})
            return True

    def control(self, action):
        if action not in ('pause', 'resume', 'stop'):
            raise ValueError('unknown control')
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            s = self._state(c)
            s['paused'] = action != 'resume'
            s['stopped'] = action == 'stop'
            self._save(c, s)
            if action == 'stop':
                c.execute("UPDATE jobs SET status='cancelled', updated=? WHERE status='queued'", (time.time(),))
            self._event(c, 'control', {'action': action})

    def remember(self, text, source='user'):
        if not isinstance(text, str) or not text.strip() or len(text) > 12000:
            raise ValueError('memory must contain 1..12000 characters')
        with self.db() as c:
            cur = c.execute('INSERT INTO memories(ts,text,source) VALUES(?,?,?)', (time.time(), text, source))
            c.execute('DELETE FROM memories WHERE id <= (SELECT MAX(id)-5000 FROM memories)')
            return cur.lastrowid

    def memories(self, query=''):
        with self.db() as c:
            return [dict(r) for r in c.execute(
                'SELECT * FROM memories WHERE instr(text,?)>0 ORDER BY id DESC LIMIT 30', (query,))]

    def enqueue(self, kind, payload):
        if kind not in ('research', 'train'):
            raise ValueError('unknown capability')
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0] >= 10:
                raise ValueError('job queue full')
            cur = c.execute("INSERT INTO jobs(created,updated,kind,status,payload) VALUES(?,?,?,'queued',?)",
                            (time.time(), time.time(), kind, json.dumps(payload)))
            return cur.lastrowid

    def claim(self):
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            s = self._state(c)
            if s['paused'] or s['stopped']:
                return None
            r = c.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY id LIMIT 1").fetchone()
            if not r:
                return None
            c.execute("UPDATE jobs SET status='running',updated=? WHERE id=?", (time.time(), r['id']))
            return {**dict(r), 'payload': json.loads(r['payload'])}

    def finish(self, job_id, result, status='completed'):
        with self.db() as c:
            c.execute('UPDATE jobs SET status=?,updated=?,result=? WHERE id=?',
                      (status, time.time(), json.dumps(result, ensure_ascii=False), job_id))
            self._event(c, 'job', {'id': job_id, 'status': status, 'result': result})

    def recover(self):
        with self.db() as c:
            c.execute("UPDATE jobs SET status='interrupted',updated=? WHERE status='running'", (time.time(),))

    def active_policy(self):
        with self.db() as c:
            v = self._state(c)['policy_version']
            r = c.execute('SELECT policy FROM policies WHERE id=?', (v,)).fetchone()
            return json.loads(r[0]) if r else {}

    def promote(self, policy, metrics):
        from .learning import validate
        validate(policy)
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            s = self._state(c)
            if s['paused'] or s['stopped']:
                return None
            cur = c.execute('INSERT INTO policies(ts,policy,metrics) VALUES(?,?,?)',
                            (time.time(), json.dumps(policy), json.dumps(metrics)))
            s['policy_version'] = cur.lastrowid
            self._save(c, s)
            self._event(c, 'evolution', {'version': cur.lastrowid, 'metrics': metrics})
            return cur.lastrowid

    def rollback(self, version):
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            if not c.execute('SELECT 1 FROM policies WHERE id=?', (version,)).fetchone() and version != 0:
                raise ValueError('unknown policy version')
            s = self._state(c)
            s['policy_version'] = version
            self._save(c, s)
            self._event(c, 'rollback', {'version': version})
