import os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'board'))
from engine import ROOT
(ROOT/'board').mkdir(parents=True,exist_ok=True)
import tkinter as tk
from app import BoardApp
if __name__=='__main__':
 import ctypes
 try:ctypes.windll.shcore.SetProcessDpiAwareness(2)
 except (AttributeError,OSError):pass
 root=tk.Tk();app=BoardApp(root)
 if '--pve-smoke-test' in sys.argv:
  import time
  deadline=time.monotonic()+90
  def verify():
   if time.monotonic()>deadline:
    (ROOT/'pve-smoke-test.failed').write_text(app.status.get(),encoding='utf-8');app.close();return
   if app.busy:
    root.after(100,verify);return
   if not app.engine:
    (ROOT/'pve-smoke-test.failed').write_text(app.status.get(),encoding='utf-8');app.close();return
   if len(app.stones)==2:
    (ROOT/'pve-smoke-test.ok').write_text('Installed CPU engine: player move + AI reply OK',encoding='utf-8');app.close();return
   if not app.stones:app.play('D4')
   root.after(200,verify)
  root.after(100,verify)
 if '--coach-smoke-test' in sys.argv:
  import time
  from coach_ui import CoachWindow
  from unittest.mock import patch
  deadline=time.monotonic()+120
  test_window=None
  def coach_check():
   global test_window
   try:
    if time.monotonic()>deadline:raise RuntimeError('coaching timeout')
    if app.busy:root.after(100,coach_check);return
    if not app.engine:raise RuntimeError('engine missing')
    if test_window is None:
     game=dict(game_id='acceptance',size=9,player_color='b',history=[['b','D4'],['w','C4'],['b','E4'],['w','D3'],['b','A1'],['w','E3'],['b','A2'],['w','F4'],['b','H8'],['w','E5'],['b','H7'],['w','D5']])
     test_window=CoachWindow(app,app.lesson_store,game,ROOT)
     app.coach_window=test_window;test_window.analyze()
    if test_window.lesson:
     lesson=test_window.lesson
     assert lesson['recommended_move'] not in test_window.message.get()
     test_window.selection=lesson['recommended_move'];test_window.answer()
     test_window.show_answer();test_window.step(1)
     assert test_window.index==1
     assert app.history==[],'lesson changed live game'
     assert app.lesson_store.due(now=time.time()+86401)
     with patch('coach_ui.filedialog.asksaveasfilename',return_value=str(ROOT/'acceptance-export.zip')):test_window.export()
     (ROOT/'coach-smoke-test.ok').write_text('CPU analysis, retry, PV, persisted retest, export and unchanged live game: PASS',encoding='utf-8')
     app.close();return
    root.after(100,coach_check)
   except Exception as exc:
    (ROOT/'coach-smoke-test.failed').write_text(str(exc),encoding='utf-8');app.close()
  root.after(100,coach_check)
 if '--smoke-test' in sys.argv:
  def finish():
   (ROOT/'smoke-test.ok').write_text('GUI startup OK',encoding='utf-8')
   app.close()
  root.after(2500,finish)
 root.mainloop()
