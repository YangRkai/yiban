import unittest
from types import SimpleNamespace
from camera_panel import CameraPanel
from test_output_worker import Value

class ManualRecovery(unittest.TestCase):
    def panel(self):
        panel=SimpleNamespace(output=Value(True),enabled=Value(True),run_status=Value(),note=Value(),waiting_manual=False,
            run_mode=Value('读盘并点击目标'),arm_output=lambda:None)
        return panel
    def test_failure_keeps_reading_and_sync_restores_clicks(self):
        p=self.panel()
        CameraPanel.click_failed(p,'D4','没有确认')
        self.assertTrue(p.enabled.get());self.assertFalse(p.output.get())
        self.assertTrue(p.waiting_manual)
        CameraPanel.resume_after_sync(p)
        self.assertTrue(p.output.get());self.assertFalse(p.waiting_manual)
    def test_stop_does_not_rearm_clicking(self):
        p=self.panel();CameraPanel.click_failed(p,'D4','未确认')
        p.enabled.set(False)
        CameraPanel.resume_after_sync(p)
        self.assertFalse(p.output.get())
