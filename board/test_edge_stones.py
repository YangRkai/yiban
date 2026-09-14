import unittest
from vision import BoardVision,cv2,np
from test_vision import scene
from engine import LETTERS

class EdgeStones(unittest.TestCase):
    def test_cropped_board_all_edges_and_corners_both_colors(self):
        for x,y in [(0,0),(18,0),(18,18),(0,18),(0,9),(18,9),(9,0),(9,18)]:
            for color in ('b','w'):
                empty,_=scene(19)
                occupied,_=scene(19,{(x,y):color})
                # OBS can crop exactly to the outer intersections.
                empty=empty[32:-31,32:-31];occupied=occupied[32:-31,32:-31]
                h,w=empty.shape[:2];corners=[(0,0),(w-1,0),(w-1,h-1),(0,h-1)]
                reader=BoardVision(19,corners,empty)
                reading=reader.read(occupied)
                with self.subTest(x=x,y=y,color=color):
                    self.assertEqual(reading.stones,{LETTERS[x]+str(19-y):color})
                    self.assertEqual(reading.unknown,0)
