import unittest,time
from pathlib import Path
from vision import BoardVision,cv2,np
from test_vision import scene

@unittest.skipUnless((Path(__file__).parent/'fixtures'/'seven-stones.png').exists(),'Private screenshot fixtures are not distributed')
class FoxStones(unittest.TestCase):
    def test_full_user_board_and_new_stones_after_calibration(self):
        frame=cv2.imread(str(Path(__file__).parent/'fixtures'/'seven-stones.png'))
        corners=[(15,130),(591,130),(591,712),(15,712)]
        expected={'F17':'b','D16':'w','R16':'b','C14':'b','G12':'w','D4':'b','R4':'w'}
        reader=BoardVision(19,corners,frame)
        self.assertEqual(reader.read(frame).stones,expected)
        # Simulate the earlier frame by replacing new-stone disks with nearby wood.
        before=frame.copy()
        for x,y in [(175,195),(79,292),(207,357),(527,615)]:
            patch=frame[y-16:y+17,x+17:x+50].copy()
            before[y-16:y+17,x-16:x+17]=patch
        reader=BoardVision(19,corners,before)
        result=reader.read(frame)
        self.assertEqual(result.stones,expected)
        self.assertEqual(result.unknown,0)
    def test_actual_stones_with_and_without_last_move_triangle(self):
        for name,color in [('black','b'),('black-last','b'),('white','w'),('white-last','w')]:
            for scale in (34,40,48):
                frame,corners=scene(19)
                reader=BoardVision(19,corners,frame)
                tile=cv2.imread(str(Path(__file__).parent/'fixtures'/f'{name}.png'))
                tile=cv2.resize(tile,(scale,scale))
                p=32+5*48;start=p-scale//2
                frame[start:start+scale,start:start+scale]=tile
                with self.subTest(name=name,scale=scale):
                    result=reader.read(frame)
                    self.assertEqual(result.stones,{'F14':color})
                    self.assertEqual(result.unknown,0)
                    self.assertEqual(result.last_move,'F14' if name.endswith('-last') else None)
