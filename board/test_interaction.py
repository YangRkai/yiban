from pathlib import Path
import time
import tkinter as tk
import unittest
import gc
from unittest.mock import patch
from app import BoardApp

@unittest.skipUnless((Path(__file__).parent/'runtime.json').exists(),'Configure local KataGo to run integration tests')
class DoubleClickFlow(unittest.TestCase):
    def setUp(self):
        errors=patch('app.messagebox.showerror');errors.start();self.addCleanup(errors.stop)
        self.devices_patch=patch('video_sources.list_sources',return_value=[]);self.devices_patch.start()
        self.save_patch=patch('camera_panel.CameraPanel.save_settings');self.save_patch.start()
        self.root=tk.Tk()
        self.app=BoardApp(self.root)
        self.app.mode.set('视频联动')
        self.root.title('弈伴交互自动测试')
        self.wait_ready()
        self.app.speed.set('极速 · 1 秒')
    def tearDown(self):
        self.app.close()
        self.app=None;self.root=None;gc.collect()
        self.devices_patch.stop();self.save_patch.stop()
    def wait_ready(self):
        until=time.monotonic()+25
        while self.app.busy and time.monotonic()<until:
            self.root.update()
            time.sleep(.02)
        self.root.update()
        self.assertFalse(self.app.busy,'引擎未按时完成操作')
    def click(self,at):
        x,y,s=self.app.geometry()
        self.app.canvas.event_generate('<ButtonPress-1>',x=int(x+3*s),y=int(y+15*s),time=at)
        self.app.canvas.event_generate('<ButtonRelease-1>',x=int(x+3*s),y=int(y+15*s),time=at+10)
        self.root.update()
    def test_single_click_commits_without_ai(self):
        self.click(1000)
        self.wait_ready()
        self.assertEqual(self.app.history,[('b','D4')])
        self.assertEqual(self.app.engine.snapshot()['stones'],{'D4':'b'})
        self.click(5000)
        self.wait_ready()
        self.assertEqual(len(self.app.history),2)
    def test_pve_replies_and_undo_returns_to_player(self):
        self.app.mode.set('本地 PVE');self.app.ai_side.set('白棋');self.app.pve_running=True
        self.app.play('D4');self.wait_ready()
        self.assertEqual(len(self.app.history),2)
        self.assertEqual(self.app.history[-1][0],'w')
        self.app.undo();self.wait_ready()
        self.assertEqual(self.app.history,[])
        self.assertEqual(self.app.next_color(),'b')
    def test_pve_black_opens_new_game_without_camera(self):
        self.app.mode.set('本地 PVE');self.app.ai_side.set('黑棋')
        self.app.new_game();self.wait_ready()
        self.assertEqual(len(self.app.history),1)
        self.assertEqual(self.app.history[0][0],'b')
        self.assertEqual(self.app.next_color(),'w')
        self.assertFalse(self.app.camera.enabled.get())
        self.assertFalse(self.app.camera.output.get())
    def test_stop_during_camera_move_does_not_schedule_ai(self):
        panel=self.app.camera;panel.side.set('白棋');panel.enabled.set(True)
        self.app.play_camera('D4',{'D4':'b'})
        self.app.stop_auto_game()
        self.wait_ready()
        self.assertEqual(self.app.history,[('b','D4')])
        self.assertFalse(panel.enabled.get());self.assertFalse(panel.output.get())

    def test_import_existing_board_turn_and_undo(self):
        self.app.open_camera()
        self.app.camera.enabled.set(True)
        self.app.camera.output.set(True)
        self.app.import_camera({'Q16':'b','D4':'w'},'w')
        self.wait_ready()
        self.assertEqual(self.app.stones,{'Q16':'b','D4':'w'})
        self.assertEqual(self.app.next_color(),'w')
        self.assertFalse(self.app.camera.enabled.get())
        self.assertFalse(self.app.camera.output.get())
        self.app.play('Q4');self.wait_ready()
        self.assertEqual(self.app.next_color(),'b')
        self.app.undo();self.wait_ready()
        self.assertEqual(self.app.stones,{'Q16':'b','D4':'w'})
        self.assertEqual(self.app.next_color(),'w')
    def test_double_click_auto_replies_once_and_busy_clicks_are_ignored(self):
        self.assertFalse(self.app.auto.get())
        self.click(2000)
        self.click(2150)
        self.assertTrue(self.app.busy)
        self.app.on_click(type('Event',(),{'x':1,'y':1})())
        self.wait_ready()
        self.assertEqual(len(self.app.history),2)
        self.assertEqual(self.app.history[0],('b','D4'))
        self.assertEqual(self.app.history[1][0],'w')
        self.assertEqual(self.app.stones,self.app.engine.snapshot()['stones'])

    def test_camera_manual_moves_and_white_only_auto_reply(self):
        self.app.open_camera()
        panel=self.app.camera
        panel.side.set('白棋');panel.enabled.set(True)
        panel.process_board({'D4':'b'})
        self.wait_ready()
        self.assertEqual(len(self.app.history),2)
        self.assertEqual(self.app.history[1][0],'w')
        panel.process_board(dict(self.app.stones))
        self.wait_ready()
        self.assertEqual(len(self.app.history),2)
        self.assertFalse(panel.output.get())

    def test_camera_black_only_does_not_generate_white(self):
        self.app.open_camera()
        panel=self.app.camera
        panel.side.set('黑棋');panel.enabled.set(True)
        panel.process_board({'D4':'b'})
        self.wait_ready()
        self.assertEqual(self.app.history,[('b','D4')])
        panel.process_board({'D4':'b','Q16':'w'})
        self.wait_ready()
        self.assertEqual(len(self.app.history),3)
        self.assertEqual(self.app.history[-1][0],'b')
        self.assertEqual(self.app.history[0],('b','D4'))
        self.assertEqual(self.app.history[1][0],'w')
        self.assertEqual(self.app.stones,self.app.engine.snapshot()['stones'])
        until=time.monotonic()+.3
        while time.monotonic()<until:self.root.update();time.sleep(.02)
        self.assertEqual(len(self.app.history),3)

if __name__=='__main__':unittest.main()
