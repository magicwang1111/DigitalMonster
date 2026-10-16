"""Finite restart/pause durability exercise; separate database from the real organism."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from digitalmon.store import Store

root = Path(__file__).resolve().parents[1] / 'artifacts' / 'soak'
root.mkdir(parents=True, exist_ok=True)
s = Store(root / 'life.sqlite')
identity = s.snapshot()['id']
start = time.time()
duration = int(sys.argv[1]) if len(sys.argv) > 1 else 1800
while time.time() - start < duration:
    s.tick()
    time.sleep(0.5)
s.control('pause')
before = s.snapshot()['ticks']
assert not s.tick()
s = Store(root / 'life.sqlite')
after = s.snapshot()
assert after['id'] == identity and after['ticks'] == before
(root / 'report.json').write_text(json.dumps({'duration_seconds': time.time()-start,
    'ticks': before, 'identity_preserved': True, 'pause_verified': True,
    'event_count_retained': len(after['events']), 'finished': time.time()}, indent=2), encoding='utf-8')
