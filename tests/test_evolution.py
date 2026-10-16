import unittest
from digitalmon.pet import stage_for

class EvolutionTests(unittest.TestCase):
    def test_care_and_exploration_unlock_form_without_changing_brain(self):
        s={'pet':{'feed_count':10,'touch_count':10},'brain':{'updates':30,'steps':1200,
             'explored_sources':['a','b','c'],'id':'same-brain'}}
        self.assertEqual(stage_for(s,[]),1)
        s['brain']['explored_sources']=[]
        self.assertEqual(stage_for(s,[]),0)
