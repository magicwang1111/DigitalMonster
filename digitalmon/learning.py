"""Measured tabular reinforcement learning on a fixed navigation terrain."""
import math
import random
import statistics
import time

from .world import CELLS, initial, key, step

EVAL_SEEDS = tuple(range(100000, 100100))


def validate(policy):
    if not isinstance(policy, dict) or not policy or len(policy) > 625:
        raise ValueError('invalid policy size')
    for k, values in policy.items():
        try:
            coords = [int(x) for x in k.split(',')]
            valid_key = len(coords) == 4 and tuple(coords[:2]) in CELLS and tuple(coords[2:]) in CELLS
        except (AttributeError, ValueError):
            valid_key = False
        if not valid_key or not isinstance(values, list) or len(values) != 4:
            raise ValueError('invalid policy state')
        if any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1000 for v in values):
            raise ValueError('invalid policy values')


def train(seed=7, episodes=4000, cancelled=lambda: False, seconds=60):
    if type(episodes) is not int or not 1 <= episodes <= 10000:
        raise ValueError('episodes must be 1..10000')
    rng, q, updates = random.Random(seed), {}, 0
    start = time.monotonic()
    completed = 0
    for episode in range(episodes):
        if episode % 20 == 0 and (cancelled() or time.monotonic() - start > seconds):
            raise InterruptedError('training cancelled or time budget exceeded')
        s = initial(rng.randrange(100000))
        epsilon = max(0.08, 0.8 * (1 - episode / episodes))
        while True:
            values = q.setdefault(key(s), [0.0] * 4)
            a = rng.randrange(4) if rng.random() < epsilon else max(range(4), key=lambda a: values[a])
            n, reward, done = step(s, a)
            target = reward + (0 if done else 0.95 * max(q.get(key(n), [0.0] * 4)))
            values[a] += 0.25 * (target - values[a])
            updates += 1
            s = n
            if done:
                break
        completed += 1
    validate(q)
    return q, {'algorithm': 'tabular Q-learning', 'seed': seed, 'episodes': completed,
               'updates': updates, 'seconds': time.monotonic()-start,
               'scope': 'fixed terrain; held-out episode seeds, not unseen state space'}


def evaluate(policy, seeds=EVAL_SEEDS):
    rewards, lengths, success = [], [], 0
    for seed in seeds:
        s, total = initial(seed), 0.0
        rng = random.Random(seed + 1000000)
        while True:
            values = policy.get(key(s))
            a = max(range(4), key=lambda a: values[a]) if values else rng.randrange(4)
            s, reward, done = step(s, a)
            total += reward
            if done:
                break
        rewards.append(total)
        lengths.append(s['age'])
        success += int(s['collected'])
    if not rewards:
        raise ValueError('empty evaluation set')
    return {'mean_reward': statistics.mean(rewards), 'success_rate': success / len(rewards),
            'mean_steps': statistics.mean(lengths), 'episodes': len(rewards),
            'min_reward': min(rewards), 'max_reward': max(rewards),
            'median_reward': statistics.median(rewards), 'rewards': rewards}


def compare(candidate, current):
    improvement = (candidate['mean_reward']-current['mean_reward']) / max(abs(current['mean_reward']), 1)
    return {'accepted': improvement >= 0.10 and candidate['success_rate'] >= current['success_rate']-0.05,
            'relative_improvement': improvement, 'candidate': candidate, 'current': current,
            'evaluation': 'fixed-terrain-v1/seeds-100000-100099',
            'gate': 'reward +10% and success rate decrease <=5 percentage points'}

