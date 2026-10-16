"""Procedural maze tasks with simulator-derived shortest-path supervision."""
from collections import deque
import random

MOVES = [(0, -1), (1, 0), (0, 1), (-1, 0)]


def solve(walls, goal):
    size = len(walls)
    distances = [[-1]*size for _ in range(size)]
    gx, gy = goal
    distances[gy][gx] = 0
    queue = deque([goal])
    while queue:
        x, y = queue.popleft()
        for dx, dy in MOVES:
            nx, ny = x+dx, y+dy
            if 0 <= nx < size and 0 <= ny < size and not walls[ny][nx] and distances[ny][nx] == -1:
                distances[ny][nx] = distances[y][x]+1
                queue.append((nx, ny))
    optimal = [[[False]*4 for _ in range(size)] for _ in range(size)]
    for y in range(size):
        for x in range(size):
            if distances[y][x] <= 0:
                continue
            for a, (dx, dy) in enumerate(MOVES):
                nx, ny = x+dx, y+dy
                optimal[y][x][a] = (0 <= nx < size and 0 <= ny < size and
                                     distances[ny][nx] == distances[y][x]-1)
    return distances, optimal


def generate(seed, size=9, density=None):
    rng = random.Random(seed)
    density = density if density is not None else rng.choice((0.08, 0.16, 0.24))
    for _ in range(100):
        walls = [[int(rng.random() < density) for _ in range(size)] for _ in range(size)]
        goal = (rng.randrange(size), rng.randrange(size))
        walls[goal[1]][goal[0]] = 0
        distances, optimal = solve(walls, goal)
        starts = [(x, y) for y in range(size) for x in range(size) if distances[y][x] >= 2]
        if starts:
            return {'seed': seed, 'walls': walls, 'goal': goal, 'start': rng.choice(starts),
                    'distances': distances, 'optimal': optimal, 'density': density}
    raise ValueError('unable to generate a reachable maze')


def rollout(maze, actions, max_steps=100):
    x, y = maze['start']
    shortest = maze['distances'][y][x]
    size, seen = len(maze['walls']), set()
    for t in range(max_steps):
        if (x, y) == tuple(maze['goal']):
            return {'success': True, 'steps': t, 'shortest': shortest}
        if (x, y) in seen:
            break  # deterministic policy loops forever from here
        seen.add((x, y))
        dx, dy = MOVES[actions[y][x]]
        nx, ny = x+dx, y+dy
        if 0 <= nx < size and 0 <= ny < size and not maze['walls'][ny][nx]:
            x, y = nx, ny
    return {'success': False, 'steps': max_steps, 'shortest': shortest}

