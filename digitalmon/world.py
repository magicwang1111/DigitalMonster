"""Small deterministic navigation laboratory. Actions: up, right, down, left."""
import random

SIZE = 5
WALLS = {(1, 1), (3, 1), (1, 3)}
CELLS = [(x, y) for y in range(SIZE) for x in range(SIZE) if (x, y) not in WALLS]
MOVES = [(0, -1), (1, 0), (0, 1), (-1, 0)]
HORIZON = 40


def initial(seed):
    rng = random.Random(seed)
    p, g = rng.sample(CELLS, 2)
    return {'position': list(p), 'goal': list(g), 'energy': HORIZON,
            'age': 0, 'seed': seed, 'collected': False}


def key(s):
    return ','.join(map(str, s['position'] + s['goal']))


def step(s, action):
    if type(action) is not int or not 0 <= action < 4:
        raise ValueError('action must be 0..3')
    if s['energy'] <= 0 or s['collected']:
        return dict(s), 0.0, True
    x, y = s['position']
    dx, dy = MOVES[action]
    nxt = (x + dx, y + dy)
    collision = nxt not in CELLS
    if collision:
        nxt = (x, y)
    collected = list(nxt) == s['goal']
    reward = 10.0 if collected else (-1.0 if collision else -0.1)
    out = {**s, 'position': list(nxt), 'energy': s['energy'] - 1,
           'age': s['age'] + 1, 'collected': collected}
    return out, reward, collected or out['energy'] <= 0

