"""Non-blocking ownership overlay, with one short-click / press-and-hold control."""
import queue
import threading
import time
import tkinter as tk
from engine import vertex_xy
from territory import PressToggle, estimate, position_key, summary_text


class TerritoryOverlay:
    def __init__(self, app, root_path, estimator=estimate):
        self.app=app;self.root=app.root;self.root_path=root_path;self.estimator=estimator
        self.gesture=PressToggle();self.events=queue.Queue();self.cancel=threading.Event()
        self.working=False;self.work_key=None;self.cache_key=None;self.result=None
        self.error_key=None;self.error='';self.closed=False;self.displayed=False
        self.observed=None;self.worker=None
        self.info=tk.Label(app.board_host,bg='#e7ede5',fg='#243c33',justify='left',anchor='w',
                           font=('Microsoft YaHei UI',9),padx=12,pady=8)
        self.info.bind('<Configure>',lambda e:self.info.configure(wraplength=max(100,e.width-24)))
        button=app.score_button
        button.configure(command=self.toggle)
        button.bind('<ButtonPress-1>',self.press)
        button.bind('<ButtonRelease-1>',self.release)
        button.bind('<Leave>',self.cancel_press)
        button.bind('<FocusOut>',self.cancel_press)
        self.timer=self.root.after(50,self.poll)

    def snapshot(self):
        a=self.app
        return dict(size=a.board_size,stones=dict(a.stones),history=list(a.history),
                    setup_stones=dict(a.setup_stones),setup_next=a.setup_next,
                    turn_override=a.turn_override,next_color=a.next_color(),game_id=a.game_id)

    def press(self,event=None):
        self.app.score_button.focus_set();self.gesture.press(time.monotonic())
        return 'break'

    def release(self,event=None):
        self.gesture.release(time.monotonic());self.changed()
        return 'break'

    def cancel_press(self,event=None):
        self.gesture.cancel();self.changed()

    def toggle(self):
        self.gesture.visible=not self.gesture.visible;self.changed()

    def changed(self):
        if self.closed:return
        if self.gesture.visible and not self.displayed:self.error_key=None
        self.displayed=self.gesture.visible
        if self.displayed:
            self.info.pack(side='bottom',fill='x',padx=8,pady=4,before=self.app.canvas)
            self.app.score_button.state(['pressed'])
        else:
            self.info.pack_forget();self.app.score_button.state(['!pressed'])
        self.app.draw()

    def poll(self):
        if self.closed:return
        self.gesture.tick(time.monotonic())
        if self.gesture.visible!=self.displayed:self.changed()
        state=self.snapshot();key=position_key(state)
        observed=(key,self.app.busy,bool(self.app.engine))
        dirty=observed!=self.observed;self.observed=observed
        if self.cache_key!=key and self.result is not None:
            self.result=None;self.cache_key=None;dirty=True
        if self.working and self.work_key!=key:self.cancel.set()
        try:
            while True:
                received,result,error=self.events.get_nowait()
                self.working=False
                if received==key and not self.cancel.is_set():
                    if error:self.error_key=key;self.error=error
                    else:self.cache_key=key;self.result=result;self.error_key=None
                    dirty=True
        except queue.Empty:pass
        if self.gesture.visible and not self.working and self.cache_key!=key and self.error_key!=key:
            if self.app.engine and not self.app.busy:
                self.working=True;self.work_key=key;self.cancel=threading.Event()
                cancel=self.cancel
                def work():
                    try:self.events.put((key,self.estimator(self.root_path,state,cancel),None))
                    except Exception as exc:self.events.put((key,None,str(exc)))
                self.worker=threading.Thread(target=work,daemon=True);self.worker.start()
        if dirty:self.paint()
        self.timer=self.root.after(50,self.poll)

    def paint(self):
        canvas=self.app.canvas;canvas.delete('territory')
        if not self.gesture.visible:return
        key=position_key(self.snapshot())
        if self.result is None or self.cache_key!=key:
            text='正在估算当前局面…（首次需加载 CPU 模型）'
            if self.app.busy:text='等待当前落子完成，再更新估算…'
            elif not self.app.engine:text='引擎尚未就绪，暂不能估算。'
            if self.error_key==key:text='估算失败：'+self.error+'；关闭后再点可重试。'
            self.info.configure(text=text);return
        self.info.configure(text=summary_text(self.result))
        x0,y0,spacing=self.app.geometry();radius=spacing*.14
        for vertex,owner in self.result['marks'].items():
            a,b=vertex_xy(vertex,self.app.board_size);x=x0+a*spacing;y=y0+b*spacing
            if owner=='?':
                canvas.create_polygon(x,y-radius,x+radius,y,x,y+radius,x-radius,y,
                                      fill='#88928a',outline='#f4f3ee',tags='territory')
            else:
                canvas.create_rectangle(x-radius,y-radius,x+radius,y+radius,
                                        fill='#111813' if owner=='b' else '#ffffff',
                                        outline='#ffffff' if owner=='b' else '#111813',tags='territory')

    def close(self):
        self.closed=True;self.cancel.set();self.root.after_cancel(self.timer)
        if self.worker:self.worker.join(timeout=3)
