import tkinter as tk
import unittest
from types import SimpleNamespace
from position_review import PositionReview
from test_vision import scene
from vision import BoardVision,Reading

class ReviewFlow(unittest.TestCase):
    def test_correct_uncertain_points_then_confirm_exact_position(self):
        root=tk.Tk();root.withdraw()
        try:
            frame,corners=scene(stones={(3,3):'b'})
            reader=BoardVision(9,corners,frame);submitted=[]
            reading=Reading({'D6':'b'},2,frame,{'A9','B9'})
            dialog=PositionReview(root,reader,frame,reading,'w',lambda s,c:submitted.append((s,c)))
            dialog.accept();self.assertEqual(submitted,[])
            dialog.mode.set('白棋');dialog.click(SimpleNamespace(x=20,y=20))
            self.assertEqual(dialog.stones['A9'],'w')
            dialog.clear_uncertain()
            self.assertEqual(dialog.uncertain,set())
            dialog.accept()
            self.assertEqual(submitted,[({'D6':'b','A9':'w'},'w')])
        finally:root.destroy()
