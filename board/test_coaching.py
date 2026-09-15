import tempfile
import unittest
from pathlib import Path
from coaching import LessonStore, verified_gap, game_sgf

class CoachingTests(unittest.TestCase):
    def test_sgf_coordinates_and_pass(self):
        self.assertEqual(game_sgf({'size':9,'history':[['b','A1'],['w','pass'],['b','resign']]}),
                         '(;GM[1]FF[4]CA[UTF-8]SZ[9]KM[7.5]RU[Chinese];B[ai];W[])')
    def test_black_white_and_unstable_estimates(self):
        self.assertEqual(verified_gap('b', [(4, 0), (5, 1)]), 4)
        self.assertEqual(verified_gap('w', [(-4, 0), (-5, -1)]), 4)
        self.assertIsNone(verified_gap('w', [(4, 0), (5, 1)]))
        self.assertIsNone(verified_gap('b', [(4, 0), (1, 0)]))
        self.assertIsNone(verified_gap('b', [(4, 0), (20, 0)]))
    def test_record_retest_and_single_lesson_per_game(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=LessonStore(Path(tmp))
            game=store.record('game', {'history':[['b','D4']], 'size':19}, 'b')
            self.assertEqual(game['player_color'],'b')
            store.save_lesson({'game_id':'game', 'recommended_move':'Q16'})
            store.attempt('game','D4',False,False,now=100)
            store.attempt('game','Q16',True,True,now=200)
            self.assertIsNone(store.due(now=300))
            self.assertEqual(store.due(now=90000)['game_id'],'game')
            store.save_lesson({'game_id':'game', 'recommended_move':'D16'})
            self.assertEqual(len(store.lessons()),1)
            self.assertEqual(len(store.lessons()[0]['attempts']),2)
