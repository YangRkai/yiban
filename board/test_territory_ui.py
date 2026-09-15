import tkinter as tk
from tkinter import ttk
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from territory import summarize, position_key
from territory_ui import TerritoryOverlay


class OverlayTests(unittest.TestCase):
    def setUp(self):
        self.root=tk.Tk();self.root.withdraw()
        host=tk.Frame(self.root);host.pack()
        canvas=tk.Canvas(host);canvas.pack()
        self.app=SimpleNamespace(root=self.root,board_host=host,canvas=canvas,score_button=ttk.Button(host),
            board_size=9,stones={},history=[],setup_stones={},setup_next='b',turn_override=None,
            game_id='one',engine=None,busy=False,next_color=lambda:'b',geometry=lambda:(20,20,30),draw=Mock())
        self.overlay=TerritoryOverlay(self.app,None)
        self.app.draw.side_effect=self.overlay.paint
        self.result=summarize(9,{},[.9]*81,4.5)
        self.root.update_idletasks()

    def tearDown(self):
        self.overlay.close();self.root.destroy()

    def test_result_after_release_does_not_show_and_short_click_reuses_it(self):
        o=self.overlay
        with patch('territory_ui.time.monotonic',return_value=1):o.press()
        o.gesture.tick(1.4);o.changed()
        with patch('territory_ui.time.monotonic',return_value=1.5):o.release()
        o.events.put((position_key(o.snapshot()),self.result,None));o.poll()
        self.assertFalse(o.gesture.visible)
        self.assertEqual(len(self.app.canvas.find_withtag('territory')),0)
        o.toggle();self.assertEqual(len(self.app.canvas.find_withtag('territory')),81)
        o.toggle();self.assertEqual(len(self.app.canvas.find_withtag('territory')),0)

    def test_stale_response_ignored_and_undo_requests_new_estimate(self):
        o=self.overlay;old=position_key(o.snapshot())
        o.events.put((old,self.result,None));o.poll();o.toggle()
        self.app.stones={'D4':'b'};self.app.history=[('b','D4')]
        o.paint();self.assertEqual(len(self.app.canvas.find_withtag('territory')),0)
        o.events.put((old,self.result,None));o.poll()
        self.assertIsNone(o.result)
        self.app.stones={};self.app.history=[];o.poll()
        self.assertNotEqual(o.cache_key,old)

    def test_failed_estimate_can_retry_by_toggling(self):
        o=self.overlay;o.toggle();key=position_key(o.snapshot())
        o.events.put((key,None,'test error'));o.poll()
        self.assertIn('test error',o.info.cget('text'))
        o.toggle();o.toggle();self.assertIsNone(o.error_key)

    def test_drag_out_cancels_press_without_click(self):
        o=self.overlay
        with patch('territory_ui.time.monotonic',return_value=1):o.press()
        o.gesture.tick(1.4);o.changed();o.cancel_press()
        with patch('territory_ui.time.monotonic',return_value=1.5):o.release()
        self.assertFalse(o.gesture.visible)
