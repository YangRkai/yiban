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
 if '--territory-smoke-test' in sys.argv:
  import time
  from territory import position_key
  deadline=time.monotonic()+90
  count_stage=0
  old_key=None
  def territory_check():
   global count_stage,old_key
   try:
    if time.monotonic()>deadline:raise RuntimeError('territory timeout')
    if app.busy:root.after(100,territory_check);return
    if not app.engine:raise RuntimeError('engine missing')
    o=app.territory
    if count_stage==0:
     app.pve_running=False;root.geometry('1050x720');o.toggle();count_stage=1
    elif count_stage==1 and o.result:
     assert len(app.canvas.find_withtag('territory'))==361
     assert app.engine.snapshot()['history']==[]
     assert o.info.winfo_rooty()+o.info.winfo_height()<=root.winfo_rooty()+root.winfo_height()
     old_key=o.cache_key;o.toggle()
     assert not app.canvas.find_withtag('territory')
     o.gesture.press(time.monotonic()-.4);o.gesture.tick(time.monotonic());o.changed()
     assert len(app.canvas.find_withtag('territory'))==361
     o.release();assert not app.canvas.find_withtag('territory')
     app.play('D4');count_stage=2
    elif count_stage==2:
     o.toggle();assert not app.canvas.find_withtag('territory');count_stage=3
    elif count_stage==3 and o.result and o.cache_key!=old_key:
     assert o.cache_key==position_key(o.snapshot())
     assert app.engine.snapshot()['history']==[('b','D4')]
     assert app.stones=={'D4':'b'}
     (ROOT/'territory-smoke-test.ok').write_text('CPU ownership, click/hold overlay, resize, auto-refresh and unchanged game: PASS',encoding='utf-8')
     app.close();return
    if o.error_key:raise RuntimeError(o.error)
    root.after(100,territory_check)
   except Exception as exc:
    (ROOT/'territory-smoke-test.failed').write_text(str(exc),encoding='utf-8');app.close()
  root.after(100,territory_check)
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
