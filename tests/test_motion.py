import unittest
from digitalmon.motion import advance

class MotionTests(unittest.TestCase):
    def test_diagonal_movement_and_target_stop(self):
        self.assertEqual(advance((0,0),(3,4),5),(3,4))
        x,y=advance((0,0),(30,40),5)
        self.assertAlmostEqual(x,3);self.assertAlmostEqual(y,4)
        self.assertEqual(advance((-100,10),(-100,10)),(-100,10))
