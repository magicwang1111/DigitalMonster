import queue
import threading
import unittest
from types import SimpleNamespace
from digitalmon.desktop import Companion

class DesktopStateTests(unittest.TestCase):
    def test_restore_from_x_preview_keeps_state_pump_running(self):
        app=Companion.__new__(Companion)
        app.stage=5;app.form_override=None;app.messages=queue.Queue();app.closed=threading.Event()
        app.messages.put(('state',{'stage':0,'form':'基尔兽','brain':{},'interactions':1,'bond':1}))
        app.load_sprite=lambda stage:setattr(app,'stage',stage)
        app.name=app.bubble=SimpleNamespace(set=lambda value:None)
        scheduled=[]
        app.root=SimpleNamespace(after=lambda *args:scheduled.append(args))
        app.pump()
        self.assertEqual(app.stage,0)
        self.assertEqual(len(scheduled),1)
