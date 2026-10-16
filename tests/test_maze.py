import unittest


class MazeTests(unittest.TestCase):
    def test_distance_and_optimal_actions_on_hand_checked_map(self):
        from digitalmon.maze import solve
        distances, actions = solve([[0, 0, 0], [0, 1, 0], [0, 0, 0]], (2, 0))
        self.assertEqual(distances[0][0], 2)
        self.assertEqual(actions[0][0], [False, True, False, False])
        self.assertEqual(distances[1][1], -1)
        self.assertEqual(distances[2][0], 4)

    def test_unreachable_and_reproducible_maps(self):
        from digitalmon.maze import generate, solve
        self.assertEqual(generate(8), generate(8))
        distances, _ = solve([[0, 1, 0], [1, 1, 0], [0, 0, 0]], (2, 0))
        self.assertEqual(distances[0][0], -1)
        for seed in range(30):
            maze = generate(seed)
            x, y = maze['start']
            self.assertGreaterEqual(maze['distances'][y][x], 2)

    def test_oracle_and_bad_policy_evaluation(self):
        from digitalmon.maze import generate, rollout
        maze = generate(123)
        policy = [[next((i for i,v in enumerate(a) if v), 0) for a in row] for row in maze['optimal']]
        result = rollout(maze, policy)
        self.assertTrue(result['success'])
        self.assertEqual(result['steps'], result['shortest'])
        bad = [[0]*9 for _ in range(9)]
        self.assertFalse(rollout(maze, bad)['success'])

