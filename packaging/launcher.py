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
 if '--smoke-test' in sys.argv:
  def finish():
   (ROOT/'smoke-test.ok').write_text('GUI startup OK',encoding='utf-8')
   app.close()
  root.after(2500,finish)
 root.mainloop()
