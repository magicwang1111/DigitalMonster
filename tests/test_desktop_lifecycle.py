import queue
import unittest

class DesktopLifecycleTests(unittest.TestCase):
    def test_second_launch_wakes_existing_instance(self):
        from digitalmon.desktop_lifecycle import InstanceBridge
        messages=queue.Queue()
        first=InstanceBridge(messages.put,port=0)
        try:
            self.assertTrue(first.notify(first.port))
            self.assertEqual(messages.get(timeout=2),'show')
        finally:first.close()

    def test_missing_instance_does_not_report_success(self):
        from digitalmon.desktop_lifecycle import InstanceBridge
        import socket
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0))
            port=sock.getsockname()[1]
        self.assertFalse(InstanceBridge.notify(port))
