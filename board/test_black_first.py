import unittest
from types import SimpleNamespace
from camera_panel import CameraPanel
from test_output_worker import Value

class BlackFirst(unittest.TestCase):
    def test_force_recovery_reimports_same_stones_with_selected_turn(self):
        panel,calls=self.panel('b')
        panel.app.stones={'D4':'b'};panel.force_reimport=True
        CameraPanel.process_board(panel,{'D4':'b'})
        self.assertEqual(calls,[('import',{'D4':'b'},'w')])
        self.assertFalse(panel.force_reimport)
    def panel(self,next_color='b',ended=False):
        calls=[]
        app=SimpleNamespace(busy=False,engine=True,stones={},history=[],next_color=lambda:next_color,
            ended=lambda:ended,ai=lambda:calls.append('ai'),import_camera=lambda s,c,**kw:calls.append(('import',s,c)))
        panel=SimpleNamespace(app=app,output_busy=False,auto_import_pending=True,awaiting_new_board=False,color=lambda:'b',
            import_turn=Value('白棋'),side=Value('黑棋'),note=Value(),resume_after_sync=lambda:None)
        return panel,calls
    def test_black_starts_on_empty_board(self):
        panel,calls=self.panel()
        CameraPanel.process_board(panel,{})
        self.assertEqual(calls,['ai'])
        self.assertEqual(panel.import_turn.get(),'黑棋')
    def test_stale_white_turn_is_reset_even_when_both_boards_empty(self):
        panel,calls=self.panel('w')
        CameraPanel.process_board(panel,{})
        self.assertEqual(calls,[('import',{},'b')])
        panel.app.next_color=lambda:'b'
        CameraPanel.process_board(panel,{})
        self.assertEqual(calls[-1],'ai')
    def test_old_ended_game_does_not_block_new_empty_game(self):
        panel,calls=self.panel('w',True)
        CameraPanel.process_board(panel,{})
        self.assertEqual(calls,[('import',{},'b')])
    def test_second_game_waits_for_empty_and_then_black_starts(self):
        panel,calls=self.panel()
        panel.awaiting_new_board=True;panel.auto_import_pending=False
        CameraPanel.process_board(panel,{'D4':'b'})
        self.assertEqual(calls,[])
        CameraPanel.process_board(panel,{})
        self.assertEqual(calls,['ai'])
        self.assertFalse(panel.awaiting_new_board)
    def test_import_drops_old_click_deduplication(self):
        panel,calls=self.panel('w',True)
        panel.last_sent=(1,'b','D4')
        CameraPanel.process_board(panel,{})
        self.assertIsNone(panel.last_sent)
