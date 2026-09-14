import unittest
import tempfile
from pathlib import Path
import numpy as np
from vision import BoardVision, StableBoard, candidate_move, cv2


def scene(size=9, stones=None):
    step=48; margin=32; edge=(size-1)*step+2*margin
    image=np.full((edge,edge,3),(125,180,215),np.uint8)
    for k in range(size):
        p=margin+k*step
        cv2.line(image,(margin,p),(edge-margin,p),(60,80,100),1)
        cv2.line(image,(p,margin),(p,edge-margin),(60,80,100),1)
    for (x,y),color in (stones or {}).items():
        cv2.circle(image,(margin+x*step,margin+y*step),19,(25,25,25) if color=='b' else (242,242,242),-1)
    return image, [(margin,margin),(edge-margin,margin),(edge-margin,edge-margin),(margin,edge-margin)]

class VisionTests(unittest.TestCase):
    def test_gray_white_stone_on_bright_yellow_board(self):
        frame,corners=scene()
        cv2.circle(frame,(32+4*48,32+4*48),19,(185,185,185),-1)
        result=BoardVision(9,corners,frame).read(frame)
        self.assertEqual(result.stones,{'E5':'w'})
    def test_occupied_calibration_reads_existing_stones(self):
        for color in ('b','w'):
            frame,corners=scene(stones={(3,3):color})
            with self.subTest(color=color):
                result=BoardVision(9,corners,frame).read(frame)
                self.assertEqual(result.stones,{'D6':color})
                self.assertEqual(result.unknown,0)
    def test_existing_stone_can_disappear_and_new_stone_appears(self):
        frame,corners=scene(stones={(3,3):'b',(6,6):'w'})
        reader=BoardVision(9,corners,frame)
        changed,_=scene(stones={(6,6):'w',(2,2):'b'})
        reading=reader.read(changed)
        self.assertEqual(reading.stones,{'G3':'w','C7':'b'})
        self.assertEqual(reading.unknown,0)
    def test_no_signal_cannot_be_calibrated_as_empty_board(self):
        empty,corners=scene()
        with self.assertRaises(ValueError):BoardVision(9,corners,np.zeros_like(empty))
    def test_video_decode_and_stable_detection(self):
        empty,corners=scene();frame,_=scene(stones={(3,5):'b'})
        reader=BoardVision(9,corners,empty);gate=StableBoard(.5)
        with tempfile.TemporaryDirectory() as folder:
            path=str(Path(folder)/'board.avi')
            writer=cv2.VideoWriter(path,cv2.VideoWriter_fourcc(*'MJPG'),10,(empty.shape[1],empty.shape[0]))
            self.assertTrue(writer.isOpened())
            for _ in range(12):writer.write(frame)
            writer.release()
            capture=cv2.VideoCapture(path);result=None
            try:
                for i in range(12):
                    ok,decoded=capture.read();self.assertTrue(ok)
                    reading=reader.read(decoded)
                    result=gate.update(reading.stones,reading.unknown,i/10)
            finally:capture.release()
            self.assertEqual(result,{'D4':'b'})
    def test_detects_both_colors_and_does_not_read_grid_as_stones(self):
        empty,corners=scene()
        reader=BoardVision(9,corners,empty)
        self.assertEqual(reader.read(empty).stones,{})
        frame,_=scene(stones={(0,0):'b',(4,4):'w',(8,8):'b'})
        result=reader.read(frame)
        self.assertEqual(result.unknown,0)
        self.assertEqual(result.stones,{'A9':'b','E5':'w','J1':'b'})
    def test_occlusion_is_not_a_valid_board(self):
        empty,corners=scene();reader=BoardVision(9,corners,empty)
        frame=empty.copy();cv2.rectangle(frame,(90,90),(220,240),(80,140,190),-1)
        self.assertGreater(reader.read(frame).unknown,0)
    def test_stability_requires_elapsed_time_and_resets_on_uncertainty(self):
        gate=StableBoard(.5)
        self.assertIsNone(gate.update({'D4':'b'},0,0))
        self.assertIsNone(gate.update({'D4':'b'},0,.3))
        self.assertEqual(gate.update({'D4':'b'},0,.6),{'D4':'b'})
        self.assertIsNone(gate.update({'D4':'b'},1,.7))
        self.assertIsNone(gate.update({'D4':'b'},0,.8))
    def test_candidate_rejects_duplicate_wrong_color_and_missing_ai(self):
        self.assertEqual(candidate_move({}, {'D4':'b'}, 'b'),'D4')
        self.assertIsNone(candidate_move({'D4':'b'},{'D4':'b'},'w'))
        self.assertIsNone(candidate_move({}, {'D4':'w'},'b'))
        self.assertIsNone(candidate_move({'D4':'b','Q16':'w'}, {'Q16':'w','C3':'b'},'b'))
        self.assertIsNone(candidate_move({}, {'D4':'b','Q16':'b'},'b'))

if __name__=='__main__':unittest.main()
