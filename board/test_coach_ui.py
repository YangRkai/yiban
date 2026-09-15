import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from coaching import LessonStore
from coach_ui import CoachWindow

class CoachUITests(unittest.TestCase):
    def test_retry_hidden_answer_and_reveal_are_recorded(self):
        with tempfile.TemporaryDirectory() as folder:
            root=tk.Tk();root.withdraw();store=LessonStore(Path(folder))
            lesson=store.save_lesson(dict(game_id='one',move_number=5,player_color='b',size=9,
                actual_move='A1',recommended_move='C5',loss_points=3,
                recommended_frames=[{}, {'C5':'b'}],actual_frames=[{}, {'A1':'b'}],
                recommended_pv=['C5'],actual_pv=['A1']))
            window=CoachWindow(SimpleNamespace(root=root),store,None,Path(folder))
            try:
                window.load(lesson)
                self.assertNotIn('C5',window.message.get())
                window.selection='B5';window.answer()
                self.assertNotIn('C5',window.message.get())
                window.show_answer();window.step(1)
                self.assertEqual(window.index,1)
                saved=store.lessons()[0]['attempts']
                self.assertEqual(len(saved),1)
                self.assertFalse(saved[0]['answer_seen'])
                self.assertFalse(saved[0]['matched_recommendation'])
                window.load(lesson);window.show_answer()
                self.assertTrue(store.lessons()[0]['attempts'][-1]['answer_seen'])
            finally:window.close();root.destroy()
