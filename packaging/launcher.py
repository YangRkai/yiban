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
 if '--smoke-test' in sys.argv:
  def finish():
   (ROOT/'smoke-test.ok').write_text('GUI startup OK',encoding='utf-8')
   app.close()
  root.after(2500,finish)
 root.mainloop()
