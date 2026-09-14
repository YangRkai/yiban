from pathlib import Path
import unittest
from engine import Engine, parse_board, vertex_xy

class BoardParsing(unittest.TestCase):
    def test_small_board_coordinates_and_invalid_edges(self):
        self.assertEqual(vertex_xy('J1', 9), (8, 8))
        self.assertEqual(vertex_xy('A9', 9), (0, 0))
        with self.assertRaises(ValueError): vertex_xy('K1', 9)
        with self.assertRaises(ValueError): vertex_xy('A10', 9)
        rows = [f'{r} ' + '. '*9 for r in range(9, 0, -1)]
        self.assertEqual(parse_board('\n'.join(rows), 9), {})
    def test_coordinates_skip_i_and_flip_rows(self):
        self.assertEqual(vertex_xy('A19'), (0, 0))
        self.assertEqual(vertex_xy('T1'), (18, 18))
        self.assertEqual(vertex_xy('J10'), (8, 9))
        with self.assertRaises(ValueError): vertex_xy('I4')

    def test_showboard_handles_adjacent_move_numbers(self):
        rows = [f'{r:2} ' + '. '*19 for r in range(19, 0, -1)]
        rows[3] = '16 . . . . . . . . . . . . . . . O2. . .'
        rows[15] = ' 4 . . . X1. . . . . . . . . . . . . . .'
        self.assertEqual(parse_board('\n'.join(rows)), {'Q16':'w', 'D4':'b'})

@unittest.skipUnless((Path(__file__).parent/'runtime.json').exists(),'Configure local KataGo to run integration tests')
class RealEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.e = Engine()
    @classmethod
    def tearDownClass(cls): cls.e.close()
    def setUp(self): self.e.reset()

    def test_capture_illegal_move_and_undo_stay_synced(self):
        for color, move in [('w','B2'),('b','A2'),('b','B1'),('b','C2'),('b','B3')]:
            self.e.play(color, move)
        self.assertNotIn('B2', self.e.snapshot()['stones'])
        before = self.e.snapshot()
        with self.assertRaises(RuntimeError): self.e.play('w','A2')
        self.assertEqual(self.e.snapshot(), before)
        self.e.undo()
        board = self.e.snapshot()['stones']
        self.assertEqual(board['B2'], 'w')
        self.assertNotIn('B3', board)

    def test_import_position_play_and_undo_preserve_setup(self):
        position={'Q16':'b','D4':'w','C3':'b'}
        state=self.e.import_position(position,'w')
        self.assertEqual(state['stones'],position)
        self.assertEqual(state['history'],[])
        self.assertEqual(state['setup_next'],'w')
        self.e.play('w','Q4')
        self.e.undo()
        self.assertEqual(self.e.snapshot()['stones'],position)
        self.e.undo()
        self.assertEqual(self.e.snapshot()['stones'],position)
        self.e.reset()
        self.assertEqual(self.e.snapshot()['setup_stones'],{})

    def test_camera_mismatch_rolls_back_and_valid_move_commits(self):
        self.e.play('b','D4')
        before=self.e.snapshot()
        with self.assertRaises(RuntimeError):
            self.e.play_observed('w','Q16',{'Q16':'w'})
        self.assertEqual(self.e.snapshot(),before)
        result=self.e.play_observed('w','Q16',{'D4':'b','Q16':'w'})
        self.assertEqual(result['stones'],{'D4':'b','Q16':'w'})

    def test_ai_move_pass_undo_and_reset(self):
        self.e.play('b','D4')
        self.e.command('kata-set-param maxVisits 32')
        move = self.e.generate('w')
        self.assertIn(move, self.e.snapshot()['stones'])
        self.e.play('b','pass')
        self.assertEqual(self.e.snapshot()['history'][-1], ('b','pass'))
        self.e.undo()
        self.assertEqual(len(self.e.snapshot()['history']), 2)
        self.e.reset()
        self.assertEqual(self.e.snapshot()['stones'], {})
        self.assertEqual(self.e.snapshot()['history'], [])

    def test_requested_thinking_time_reaches_engine(self):
        self.e.command('kata-set-param maxVisits 32')
        self.e.generate('b', seconds=1.0)
        self.assertEqual(float(self.e.command('kata-get-param maxTime')), 1.0)
        before = self.e.snapshot()
        with self.assertRaises(ValueError): self.e.generate('w', seconds=-1)
        self.assertEqual(self.e.snapshot(), before)

    def test_board_resize_updates_engine_coordinates_and_clears_history(self):
        for size,corner in [(9,'J9'), (13,'N13'), (19,'T19')]:
            self.e.reset(size)
            self.e.play('b',corner)
            state = self.e.snapshot()
            self.assertEqual(state['size'],size)
            self.assertEqual(state['stones'],{corner:'b'})
            self.e.reset(size)
            self.assertEqual(self.e.snapshot()['history'],[])
        with self.assertRaises(ValueError):self.e.reset(10)
        self.assertEqual(self.e.snapshot()['size'],19)

if __name__ == '__main__': unittest.main()
