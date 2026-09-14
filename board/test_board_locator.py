import unittest
import numpy as np
from board_locator import locate_board
from test_vision import scene
from vision import cv2,BoardVision

class LocatorTests(unittest.TestCase):
    def test_fox_title_border_is_not_first_grid_row(self):
        from pathlib import Path
        path=Path(__file__).parent/'fixtures'/'fox-title-border.png'
        if not path.exists():self.skipTest('Private screenshot fixture is not distributed')
        frame=cv2.imread(str(path))[:710,:1180]
        corners=locate_board(frame,19)
        self.assertAlmostEqual(corners[0][1],46,delta=2)
        reading=BoardVision(19,corners,frame).read(frame)
        self.assertEqual(reading.stones,{'C17':'b','F17':'b','Q17':'b','D16':'w','P16':'w','R16':'b','C14':'b','M13':'w','G12':'w','D4':'b','R4':'w'})
        self.assertEqual(reading.unknown,0)
    def test_sizes_with_existing_stones(self):
        for size in (9,13,19):
            frame,corners=scene(size,{(3,3):'b',(5,5):'w'})
            actual=locate_board(frame,size)
            self.assertTrue(np.allclose(actual,corners,atol=2))
            self.assertEqual(len(BoardVision(size,actual,frame).read(frame).stones),2)
    def test_offset_and_resize(self):
        frame,corners=scene(19)
        frame=cv2.resize(frame,None,fx=.6,fy=.6)
        canvas=np.zeros((700,900,3),np.uint8)
        h,w=frame.shape[:2];canvas[61:61+h,123:123+w]=frame
        actual=locate_board(canvas,19)
        expected=np.asarray(corners)*.6+[123,61]
        self.assertTrue(np.allclose(actual,expected,atol=2))
    def test_blank_is_rejected(self):
        with self.assertRaises(ValueError):locate_board(np.full((480,640,3),180,np.uint8),19)
