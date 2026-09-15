import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

class LayoutTests(unittest.TestCase):
    def test_actions_stay_inside_window_at_supported_small_size(self):
        from app_layout import build_layout
        root=tk.Tk()
        app=SimpleNamespace(root=root,mode=tk.StringVar(value='本地 PVE'),status=tk.StringVar(value='就绪'),
            turn=tk.StringVar(value='轮到黑棋'),bigmove=tk.StringVar(value='—'),
            difficulty=tk.StringVar(value='休闲'),ai_side=tk.StringVar(value='白棋'))
        for name in ('toggle_settings','start_auto_game','stop_auto_game','new_game','undo','pass_move','save','ai','open_coach','draw','on_click','hover'):
            setattr(app,name,Mock())
        try:
            build_layout(app);root.geometry('1050x720');root.update()
            self.assertGreater(app.canvas.winfo_width(),400)
            for widget in app.buttons+[app.lesson_button,app.main_notice]:
                self.assertTrue(widget.winfo_ismapped())
                self.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(),root.winfo_rooty()+root.winfo_height())
            self.assertEqual(app.settings_window.state(),'withdrawn')
        finally:root.destroy()
