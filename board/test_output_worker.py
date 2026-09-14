import unittest,threading,queue,time
from types import SimpleNamespace
from camera_panel import CameraPanel

class Value:
    def __init__(self,value=None):self.value=value
    def get(self):return self.value
    def set(self,value):self.value=value

class OutputWorker(unittest.TestCase):
    def test_click_wait_does_not_block_caller_and_can_cancel(self):
        entered=threading.Event()
        def click(color,vertex,before,cancel):
            entered.set();cancel.wait(2)
        panel=SimpleNamespace(output=Value(True),color=lambda:'w',last_sent=None,
            app=SimpleNamespace(history=[('w','D4')],board_size=19,status=Value()),
            output_busy=False,target=SimpleNamespace(size=19,click_move=click),
            note=Value(),output_results=queue.Queue())
        start=time.monotonic();CameraPanel.on_ai(panel,'w','D4',{})
        self.assertLess(time.monotonic()-start,.5)
        self.assertTrue(entered.wait(1));self.assertTrue(panel.output_busy)
        panel.output_cancel.set()
        token,vertex,error=panel.output_results.get(timeout=2)
        self.assertEqual(vertex,'D4');self.assertTrue(token.is_set())
