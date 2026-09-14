import unittest
from vision import TemporalBoard,Reading

class TemporalTests(unittest.TestCase):
    def test_same_frame_cannot_confirm_twice_or_stay_fresh_forever(self):
        gate=TemporalBoard(9);reading=Reading({'D4':'b'},0,None)
        gate.update(reading,0,frame_id=1)
        self.assertIn('D4',gate.update(reading,.15,frame_id=1).uncertain)
        self.assertEqual(gate.update(reading,.3,frame_id=2).unknown,0)
        self.assertIn('D4',gate.update(reading,.9,frame_id=2).uncertain)
    def test_brief_flicker_expires_and_recovers(self):
        gate=TemporalBoard(9)
        clear=Reading({'D4':'b'},0,None)
        self.assertGreater(gate.update(clear,0).unknown,0)
        self.assertEqual(gate.update(clear,.15).unknown,0)
        flicker=Reading({},1,None,{'D4'})
        self.assertEqual(gate.update(flicker,.3).stones,{'D4':'b'})
        self.assertIn('D4',gate.update(flicker,.8).uncertain)
        self.assertIn('D4',gate.update(clear,.95).uncertain)
        self.assertEqual(gate.update(clear,1.1).unknown,0)
    def test_capture_must_be_confirmed_not_hidden_by_history(self):
        gate=TemporalBoard(9)
        stone=Reading({'D4':'b'},0,None)
        gate.update(stone,0);gate.update(stone,.15)
        empty=Reading({},0,None)
        self.assertIn('D4',gate.update(empty,.3).uncertain)
        confirmed=gate.update(empty,.45)
        self.assertEqual(confirmed.stones,{})
        self.assertEqual(confirmed.unknown,0)
