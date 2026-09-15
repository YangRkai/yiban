import unittest
from territory import PressToggle, summarize, position_key, analysis_position


class GestureTests(unittest.TestCase):
    def test_click_toggles_and_hold_release_always_hides(self):
        g=PressToggle()
        g.press(0);g.release(.1);self.assertTrue(g.visible)
        g.press(1);g.release(1.1);self.assertFalse(g.visible)
        g.press(2);g.tick(2.36);self.assertTrue(g.visible)
        g.release(2.5);self.assertFalse(g.visible)
        g.press(3);g.release(3.1)
        g.press(4);g.tick(4.4);g.release(4.5);self.assertFalse(g.visible)

    def test_delayed_timer_release_and_cancel_do_not_latch(self):
        g=PressToggle();g.press(0);g.release(.5);self.assertFalse(g.visible)
        g.press(1);g.tick(1.4);g.cancel();self.assertFalse(g.visible)
        g.release(1.5);self.assertFalse(g.visible)


class CountTests(unittest.TestCase):
    def test_orientation_threshold_and_dead_stone_accounting(self):
        values=[0.0]*81
        values[0]=.9;values[1]=.9;values[2]=.9;values[-1]=-.9
        result=summarize(9,{'A9':'b','C9':'w','J1':'w'},values,-2.5)
        self.assertEqual(result['marks']['A9'],'b')
        self.assertEqual(result['marks']['J1'],'w')
        self.assertEqual(result['b'],dict(stones=1,empty=1,dead=1,total=3))
        self.assertEqual(result['w']['total'],1)
        self.assertEqual(result['uncertain'],77)
        self.assertEqual(result['lead'],-2.5)

    def test_reject_bad_results_instead_of_counting(self):
        for values in ([0]*80,[float('nan')]*81,[1.1]*81):
            with self.assertRaises(ValueError):summarize(9,{},values,0)

    def test_history_turn_size_and_new_game_invalidate_key(self):
        s=dict(size=9,stones={'D4':'b'},history=[('b','D4')],setup_stones={},setup_next='b',next_color='w',game_id='a')
        for patch in ({'next_color':'b'},{'size':13},{'game_id':'b'},{'history':[('b','D4'),('w','pass')]},{'stones':{}}):
            self.assertNotEqual(position_key(s),position_key(dict(s,**patch)))
        normal=analysis_position(s)
        self.assertEqual(normal['history'],[('b','D4')])
        overridden=analysis_position(dict(s,turn_override='b',next_color='b'))
        self.assertEqual(overridden['history'],[])
        self.assertEqual(overridden['setup_stones'],{'D4':'b'})
        self.assertEqual(overridden['setup_next'],'b')
