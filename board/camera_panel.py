"""Camera preview and calibrated input/output controls for the local board."""
import threading,time,queue
import json
from engine import ROOT
import tkinter as tk
from tkinter import ttk,messagebox
import numpy as np
from PIL import Image,ImageTk
from vision import cv2,BoardVision,StableBoard,candidate_move,TemporalBoard

class CornerPicker:
    def __init__(self,parent,frame,callback,title):
        self.frame=frame.copy();self.callback=callback;self.points=[]
        self.window=tk.Toplevel(parent);self.window.title(title)
        tk.Label(self.window,text='有子棋盘也可：依次点击 左上 → 右上 → 右下 → 左下 的最外侧交叉点（不是棋盘边框）',font=('Microsoft YaHei UI',10)).pack(padx=12,pady=10)
        h,w=frame.shape[:2];self.scale=min(880/w,560/h,1)
        rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
        self.photo=ImageTk.PhotoImage(Image.fromarray(rgb).resize((round(w*self.scale),round(h*self.scale))))
        self.canvas=tk.Canvas(self.window,width=self.photo.width(),height=self.photo.height(),highlightthickness=0)
        self.canvas.pack(padx=10,pady=5);self.canvas.create_image(0,0,image=self.photo,anchor='nw')
        self.canvas.bind('<Button-1>',self.click)
        self.hint=tk.StringVar(value='请点击左上角交叉点')
        tk.Label(self.window,textvariable=self.hint).pack(pady=8)
        ttk.Button(self.window,text='重新选点',command=self.reset).pack(pady=(0,10))
    def reset(self):self.points=[];self.canvas.delete('point');self.hint.set('请点击左上角交叉点')
    def click(self,e):
        self.points.append((e.x/self.scale,e.y/self.scale))
        self.canvas.create_oval(e.x-5,e.y-5,e.x+5,e.y+5,fill='#ed5f32',tags='point')
        if len(self.points)<4:self.hint.set('下一点：'+['左上','右上','右下','左下'][len(self.points)]);return
        try:self.callback(self.points,self.frame)
        except Exception as error:messagebox.showerror('标定失败',str(error),parent=self.window);self.reset();return
        self.window.destroy()

class CameraPanel:
    def __init__(self,app):
        self.app=app;self.embedded=hasattr(app,'video_host')
        self.window=tk.Frame(app.video_host) if self.embedded else tk.Toplevel(app.root)
        if self.embedded:self.window.pack(fill='both',expand=True)
        else:self.window.title('弈伴 · 视频读盘');self.window.geometry('950x760')
        self.closed=False
        settings=app.settings_host if self.embedded else self.window
        notices=app.notice_host if self.embedded else self.window
        self.frame=None;self.frame_time=0;self.lock=threading.Lock();self.stop=threading.Event();self.thread=None
        self.reader=None;self.gate=StableBoard(.6);self.target=None;self.rejected=None;self.last_sent=None
        self.enabled=tk.BooleanVar(value=False);self.output=tk.BooleanVar(value=False)
        self.side=app.ai_side if hasattr(app,'ai_side') else tk.StringVar(value='白棋');self.device=tk.StringVar(value='')
        self.devices={};self.source_generation=0;self.source_error='';self.source_name=''
        self.output_results=queue.Queue();self.output_cancel=threading.Event();self.output_busy=False
        self.temporal=None;self.temporal_reader=None;self.uncertain_since=None
        self.detected_turn=None;self.turn_candidate=None;self.turn_since=0
        self.source_started=0
        self.automation_epoch=0
        self.waiting_manual=False
        self.awaiting_new_board=False
        self.auto_import_pending=False
        self.locate_pending=False
        self.source_status=tk.StringVar(value='视频未连接：选择视频源即可连接；默认 OBS 请点击“打开 / 切换”。')
        self.read_status=tk.StringVar(value='识别尚未标定；已有棋子也可。')
        self.note=tk.StringVar(value='连接视频，标定棋盘四角（允许已有棋子），选择轮到哪方并导入当前局面。')
        self.notice=tk.Label(notices,textvariable=self.note,anchor='w',justify='left',wraplength=910,font=('Microsoft YaHei UI',11),bg='#fff0cd',fg='#493514',padx=10,pady=8)
        self.notice.pack(fill='x',padx=8,pady=(8,4))
        self.notice.bind('<Configure>',lambda e:self.notice.configure(wraplength=max(160,e.width-24)))
        bar=ttk.Frame(settings);bar.pack(fill='x',padx=12,pady=8)
        ttk.Label(bar,text='视频源').pack(side='left')
        self.device_box=ttk.Combobox(bar,textvariable=self.device,width=27,state='readonly')
        self.device_box.pack(side='left',padx=6)
        self.device_box.bind('<<ComboboxSelected>>',self.select_source)
        ttk.Button(bar,text='刷新设备',command=self.refresh_devices).pack(side='left',padx=3)
        ttk.Button(bar,text='打开 / 切换',command=self.start).pack(side='left',padx=3)
        ttk.Button(bar,text='自动定位输入',command=self.calibrate).pack(side='left',padx=3)
        ttk.Button(bar,text='手动四角',command=lambda:self.calibrate(manual=True)).pack(side='left')
        ttk.Button(bar,text='暂停全部自动 (F8)',command=self.pause).pack(side='right')
        ttk.Label(self.window,textvariable=self.source_status,wraplength=910).pack(fill='x',padx=12)
        ttk.Label(self.window,textvariable=self.read_status,wraplength=910).pack(fill='x',padx=12)
        controls=ttk.Frame(settings);controls.pack(fill='x',padx=12,pady=5)
        ttk.Label(controls,text='AI 执子').pack(side='left')
        ttk.Combobox(controls,textvariable=self.side,values=['黑棋','白棋'],width=6,state='readonly').pack(side='left',padx=6)
        self.run_mode=tk.StringVar(value='读盘并点击目标')
        ttk.Combobox(controls,textvariable=self.run_mode,values=['读盘并点击目标','只读盘并计算'],state='readonly',width=18).pack(side='left',padx=6)
        ttk.Button(controls,text='启动自动',command=self.start_auto).pack(side='left',padx=6)
        ttk.Button(controls,text='停止自动',command=self.pause).pack(side='left',padx=6)
        self.run_status=tk.StringVar(value='已停止')
        ttk.Label(self.window,textvariable=self.run_status).pack(fill='x',padx=12)
        targetbar=ttk.Frame(settings);targetbar.pack(fill='x',padx=12,pady=5)
        self.target_name=tk.StringVar()
        self.window_box=ttk.Combobox(targetbar,textvariable=self.target_name,state='readonly',width=48)
        self.window_box.pack(side='left',fill='x',expand=True)
        self.window_box.bind('<<ComboboxSelected>>',self.target_changed)
        ttk.Button(targetbar,text='刷新窗口',command=self.list_targets).pack(side='left',padx=4)
        ttk.Button(targetbar,text='自动定位目标',command=self.calibrate_target).pack(side='left')
        importbar=ttk.Frame(settings);importbar.pack(fill='x',padx=12)
        ttk.Label(importbar,text='当前轮到').pack(side='left')
        self.import_turn=tk.StringVar(value='白棋')
        ttk.Combobox(importbar,textvariable=self.import_turn,values=['黑棋','白棋'],state='readonly',width=6).pack(side='left',padx=6)
        ttk.Button(importbar,text='导入当前局面',command=self.import_current).pack(side='left')
        ttk.Label(importbar,text='先核对绿圈与棋子；导入后再开启自动。').pack(side='left',padx=6)
        self.preview=tk.Label(self.window,bg='#202923',text='等待 OBS 视频',fg='white',width=1,height=1);self.preview.pack(fill='both',expand=True,padx=12,pady=8)
        if not self.embedded:self.window.protocol('WM_DELETE_WINDOW',self.close)
        self.refresh_devices()
        self.saved_input=None;self.restore_pending=False
        self.config_path=ROOT/'board'/'camera-settings.json'
        try:
            saved=json.loads(self.config_path.read_text(encoding='utf-8'))
            self.saved_input=saved.get('input')
            if saved.get('device') in self.devices:self.device.set(saved['device'])
            if not hasattr(app,'ai_side') and saved.get('side') in ('黑棋','白棋'):self.side.set(saved['side'])
            if saved.get('turn') in ('黑棋','白棋'):self.import_turn.set(saved['turn'])
            self.restore_pending=True
            if self.device.get():self.window.after(200,self.start)
        except (OSError,ValueError,TypeError):pass
        self.timer=self.window.after(150,self.tick)
    def save_settings(self):
        data={'device':self.device.get(),'side':self.side.get(),'turn':self.import_turn.get(),'input':self.saved_input}
        self.config_path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    def color(self):return {'黑棋':'b','白棋':'w'}.get(self.side.get())
    def start_auto(self):
        if self.app.busy or self.output_busy:
            self.note.set('当前任务尚未结束，请稍候再启动自动。');return
        self.awaiting_new_board=False;self.waiting_manual=False
        self.temporal=None;self.temporal_reader=None;self.last_sent=None;self.rejected=None
        if self.reader is None:self.calibrate()
        if self.run_mode.get()=='读盘并点击目标' and self.target is None:
            if self.window_box.current()<0:self.list_targets()
            if self.window_box.current()>=0:self.calibrate_target()
        self.enabled.set(True);self.arm_input()
        if not self.enabled.get():
            self.run_status.set('未启动：'+self.note.get());return
        self.output.set(self.run_mode.get()=='读盘并点击目标')
        if self.output.get():
            self.arm_output()
            if not self.output.get():
                self.enabled.set(False);self.run_status.set('未启动：'+self.note.get());return
        self.run_status.set('运行中：'+self.run_mode.get()+' · AI '+self.side.get())
        self.auto_import_pending=True;self.gate=StableBoard(1.0)
        self.note.set('自动已启动：画面稳定 1 秒后自动同步已有局面，再继续下棋。')
    def recover_current(self):
        self.pause()
        epoch=self.automation_epoch
        self.note.set('正在停止旧任务，随后重新读盘并继续…')
        def resume():
            if self.closed or epoch!=self.automation_epoch:return
            if self.app.busy or self.output_busy:
                self.window.after(100,resume);return
            self.force_reimport=True
            self.start_auto()
        resume()
    def should_reply(self):return (self.enabled.get() or self.output.get()) and self.color()==self.app.next_color()
    def pause(self):
        self.automation_epoch+=1
        self.awaiting_new_board=False
        self.auto_import_pending=False
        self.waiting_manual=False
        self.output_cancel.set()
        self.enabled.set(False);self.output.set(False);self.note.set('已暂停自动读盘和点击，仍可手动操作。')
        if hasattr(self,'run_status'):self.run_status.set('已停止')
    def reset_for_new_game(self):
        was_running=self.enabled.get()
        was_output=self.output.get()
        self.pause()
        self.gate=StableBoard(.6);self.temporal=None;self.temporal_reader=None
        self.rejected=None;self.last_sent=None;self.uncertain_since=None
        self.import_turn.set('黑棋')
        self.awaiting_new_board=was_running
        if was_running:
            self.enabled.set(True);self.output.set(was_output)
            self.note.set('等待视频出现新局空棋盘；确认后自动续开，AI 执黑会先下。')
            self.run_status.set('自动运行 · 等待新局')
        else:self.note.set('新局已准备；点击开始自动即可运行。')
    def arm_input(self):
        frame,stamp=self.latest()
        if self.enabled.get() and (frame is None or time.monotonic()-stamp>2):
            self.enabled.set(False);self.note.set('尚未收到视频画面：请在 OBS 启动虚拟摄像机，再点“打开 / 切换”。');return
        if self.enabled.get() and (self.reader is None or self.color() is None):
            self.enabled.set(False);self.note.set('请先标定摄像头棋盘，并选择 AI 执黑或执白。')
        self.gate=StableBoard(.6);self.rejected=None
    def arm_output(self):
        if self.output.get() and (not self.target or not self.target.reader or self.color() is None):
            self.output.set(False);self.note.set('请先标定目标棋盘，并选择 AI 执黑或执白。')
    def refresh_devices(self):
        from video_sources import list_sources,choose_default
        try:items=list_sources()
        except Exception as e:self.note.set('读取视频设备失败：'+str(e));return
        previous=self.device.get();self.devices=dict(items)
        self.device_box['values']=list(self.devices)
        self.device.set(previous if previous in self.devices else choose_default(items))
        if not self.device.get():self.note.set('未找到 OBS Virtual Camera。请先在 OBS 启动虚拟摄像机，然后刷新设备；不会自动选择硬件采集卡。')
        else:self.note.set('已选择 '+self.device.get()+'；请在 OBS 启动虚拟摄像机，再点击打开 / 切换。')
    def select_source(self,event=None):
        self.start()
    def start(self):
        label=self.device.get()
        if label not in self.devices:self.note.set('请先选择视频源；没有 OBS 时请先启动其虚拟摄像机并刷新。');return
        index=self.devices[label]
        self.pause();self.reader=None;self.gate=StableBoard(.6);self.stop.set()
        self.source_generation+=1;generation=self.source_generation;self.source_error=''
        self.source_started=time.monotonic();self.source_status.set('正在连接 '+label+'…')
        self.locate_pending=True
        with self.lock:self.frame=None;self.frame_time=0
        self.preview.configure(image='',text='正在切换到 '+label)
        self.note.set('正在释放旧设备并打开 '+label+'…')
        self.wait_source(index,label,generation,0)
    def wait_source(self,index,label,generation,attempt):
        if self.closed or generation!=self.source_generation:return
        if self.thread and self.thread.is_alive():
            if attempt>=60:
                self.source_error='旧视频源未释放，请关闭此面板后重新打开。';self.note.set(self.source_error);return
            self.window.after(50,lambda:self.wait_source(index,label,generation,attempt+1));return
        stop=threading.Event();self.stop=stop;self.source_name=label
        def capture():
            cap=None
            try:
                cap=cv2.VideoCapture(index,cv2.CAP_DSHOW)
                if not cap.isOpened():raise RuntimeError('无法打开 '+label+'，请确认 OBS 已启动虚拟摄像机且未被其他程序占用')
                if 'OBS' not in label.upper():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH,1280);cap.set(cv2.CAP_PROP_FRAME_HEIGHT,720)
                while not stop.is_set():
                    ok,frame=cap.read()
                    if not ok:raise RuntimeError(label+' 未返回画面，请检查 OBS 虚拟摄像机是否正在输出')
                    with self.lock:
                        if not stop.is_set() and generation==self.source_generation:self.frame=frame;self.frame_time=time.monotonic()
            except Exception as e:
                if generation==self.source_generation:self.source_error=str(e)
            finally:
                if cap is not None:cap.release()
        self.thread=threading.Thread(target=capture,daemon=True);self.thread.start()
    def latest(self):
        with self.lock:return (None if self.frame is None else self.frame.copy()),self.frame_time
    def calibrate(self,manual=False):
        frame,stamp=self.latest()
        if frame is None or time.monotonic()-stamp>2:self.note.set('尚无可用视频画面。请在 OBS 启动虚拟摄像机，再点“打开 / 切换”，看到棋盘后再标定。');return
        self.enabled.set(False)
        self.output.set(False);self.reader=None
        def accept(corners,image):
            self.reader=BoardVision(self.app.board_size,corners,image)
            self.saved_input={'corners':corners,'size':self.app.board_size,'shape':list(image.shape),'device':self.device.get()}
            self.save_settings()
            self.gate=StableBoard(.6);self.note.set('定位完成。核对绿色圈，选择当前轮到哪方，再点击“导入当前局面”。')
        if manual:CornerPicker(self.window,frame,accept,'标定摄像头 · 已有棋子也可')
        else:
            from board_locator import locate_board
            try:accept(locate_board(frame,self.app.board_size),frame)
            except ValueError as e:self.note.set(str(e))
    def import_current(self):
        if self.app.busy or not self.app.engine:
            self.note.set('请等待引擎完成当前操作。');return
        frame,stamp=self.latest()
        if self.reader is None or frame is None or time.monotonic()-stamp>2:
            self.note.set('请先连接视频并标定棋盘四角。');return
        reading=self.reader.read(frame)
        self.pause()
        from position_review import PositionReview
        review_size=self.reader.size
        def submit(stones,next_color):
            if self.app.busy or self.closed or self.app.board_size!=review_size:
                self.note.set('当前引擎忙碌或棋盘路数已变化，请重新核对。');return False
            self.gate=StableBoard(.6);self.rejected=None;self.last_sent=None
            self.app.import_camera(stones,next_color)
            self.note.set(f'已确认并提交 {len(stones)} 颗棋子；导入完成后可开启自动。')
            return True
        PositionReview(self.window,self.reader,frame,reading,{'黑棋':'b','白棋':'w'}[self.import_turn.get()],submit)
        self.note.set('请在“核对并修正局面”窗口处理橙框，再点击“确认局面并导入”。')

    def target_changed(self,event=None):
        self.pause();self.target=None
    def list_targets(self):
        from window_output import windows
        self.targets=windows()
        self.window_box['values']=[f'{title}  [{hwnd}]' for hwnd,title in self.targets]
        matches=[i for i,(_,title) in enumerate(self.targets) if '房间' in title]
        if len(matches)==1:self.window_box.current(matches[0])
        else:self.window_box.set('')
        self.target=None;self.output.set(False)
    def calibrate_target(self):
        from window_output import WindowBoard
        index=self.window_box.current()
        if index<0:self.note.set('先刷新并选择目标棋盘窗口。');return
        self.output.set(False)
        hwnd,title=self.targets[index]
        target=WindowBoard(hwnd,title)
        try:frame=target.capture()
        except Exception as e:self.note.set(str(e));return
        self.window.lift()
        def accept(corners,image):
            target.calibrate(self.app.board_size,corners,image);self.target=target
            self.note.set('目标自动定位完成：'+title+'。点击启动自动即可运行。')
        from board_locator import locate_board
        try:accept(locate_board(frame,self.app.board_size),frame)
        except ValueError as e:
            self.note.set(str(e))
            CornerPicker(self.window,frame,accept,'自动定位失败 · 手动定位目标')
    def tick(self):
        if self.closed:return
        try:
            while not self.output_results.empty():
                token,vertex,error=self.output_results.get_nowait()
                self.output_busy=False
                if token.is_set():continue
                if error:
                    self.click_failed(vertex,error)
                    self.app.status.set(self.note.get())
                else:
                    self.note.set(f'目标已确认 {vertex}，等待视频局面同步。')
                    self.app.status.set(self.note.get())
            if not self.enabled.get() and not self.output.get():self.run_status.set('已停止')
            import ctypes
            if ctypes.windll.user32.GetAsyncKeyState(0x77):self.pause()
            frame,stamp=self.latest()
            if frame is None:
                if self.source_error:self.source_status.set('连接失败：'+self.source_error)
                elif self.source_started and time.monotonic()-self.source_started>10:
                    self.source_status.set('尚未收到视频帧：检查 OBS 的“启动虚拟摄像机”，然后重新打开 / 切换。')
            elif time.monotonic()-stamp>2:
                self.source_status.set('视频已断流：'+(self.source_error or self.source_name))
                self.pause();self.note.set('视频画面中断，自动读盘和点击已暂停。')
            else:
                self.source_status.set(f'视频已连接：{self.source_name} · {frame.shape[1]} × {frame.shape[0]}')
                if self.restore_pending:
                    self.restore_pending=False
                    saved=self.saved_input
                    if saved and saved.get('shape')==list(frame.shape) and saved.get('device')==self.device.get() and saved.get('size')==self.app.board_size:
                        self.reader=BoardVision(self.app.board_size,saved['corners'],frame)
                        self.note.set('已自动读取上次输入标定。请导入当前局面后开启自动。')
                    elif saved:self.note.set('已读取设置，但视频尺寸、设备或路数变化，请重新标定输入。')
                if self.reader and self.reader.size!=self.app.board_size:
                    self.reader=None;self.pause();self.note.set('棋盘格数变化，请重新标定输入和目标棋盘。');self.target=None
                if self.locate_pending:
                    self.locate_pending=False
                    from board_locator import locate_board
                    try:
                        corners=locate_board(frame,self.app.board_size)
                        self.reader=BoardVision(self.app.board_size,corners,frame)
                        self.saved_input={'corners':corners,'size':self.app.board_size,'shape':list(frame.shape),'device':self.device.get()}
                        self.save_settings()
                        self.note.set('视频棋盘已自动定位。')
                    except ValueError:
                        self.reader=None
                        self.note.set('未自动找到完整棋盘；请显示完整棋盘后点击自动定位输入，或使用手动四角。')
                if self.reader:
                    raw=self.reader.read(frame)
                    if self.temporal_reader is not self.reader:
                        self.temporal=TemporalBoard(self.app.board_size);self.temporal_reader=self.reader
                    reading=self.temporal.update(raw,time.monotonic(),frame_id=stamp)
                    hint=None
                    if not reading.unknown:
                        if not reading.stones:hint='b'
                        elif reading.last_move in reading.stones:hint='w' if reading.stones[reading.last_move]=='b' else 'b'
                        if self.target:
                            try:hint=self.target.turn_hint() or hint
                            except (RuntimeError,OSError):pass
                    now=time.monotonic()
                    if hint!=self.turn_candidate:self.turn_candidate=hint;self.turn_since=now
                    self.detected_turn=hint if hint and now-self.turn_since>=.5 else None

                    black=sum(c=='b' for c in reading.stones.values());white=sum(c=='w' for c in reading.stones.values())
                    self.read_status.set(f'识别结果：黑 {black} 子 / 白 {white} 子 / 不确定 {reading.unknown} 处；本地 {len(self.app.stones)} 子。请核对绿色圈是否覆盖每颗棋子。')
                    display=reading.image
                    stable=self.gate.update(reading.stones,reading.unknown,time.monotonic())
                    if self.enabled.get():
                        if reading.unknown:
                            now=time.monotonic()
                            if self.uncertain_since is None:self.uncertain_since=now
                            if now-self.uncertain_since>2:
                                points='、'.join(sorted(reading.uncertain)[:12])
                                message=f'正在持续重读：{points} 仍不清晰；画面恢复后自动继续，无需重新导入。'
                                self.note.set(message);self.app.status.set(message)
                            else:self.note.set('正在等待连续清晰画面，自动重读中…')
                        else:
                            self.uncertain_since=None
                            if stable is not None:self.process_board(stable)
                else:
                    display=frame
                    if float(np.median(cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)))<15:
                        self.note.set(self.source_name+'：画面过暗或无信号，请检查 OBS 画面输出或切换视频源。')
                    else:self.note.set(self.source_name+' 已接入。请将完整棋盘放入画面，再点击“标定输入”。')
                h,w=display.shape[:2];scale=min(max(100,self.preview.winfo_width()-12)/w,max(100,self.preview.winfo_height()-12)/h)
                rgb=cv2.cvtColor(display,cv2.COLOR_BGR2RGB)
                self.photo=ImageTk.PhotoImage(Image.fromarray(rgb).resize((round(w*scale),round(h*scale))))
                self.preview.configure(image=self.photo,text='')
        except Exception as e:
            self.pause();self.note.set('识别暂停：'+str(e))
        self.timer=self.window.after(150,self.tick)
    def process_board(self,observed):
        app=self.app
        if self.output_busy or app.busy or not app.engine or self.color() is None:return
        if self.awaiting_new_board:
            if observed:return
            self.awaiting_new_board=False;self.auto_import_pending=True
        if app.ended() and not observed:
            self.auto_import_pending=True
        if self.auto_import_pending:
            self.auto_import_pending=False
            if not observed:
                self.import_turn.set('黑棋')
            forced=getattr(self,'force_reimport',False);self.force_reimport=False
            if forced or observed!=app.stones or app.ended() or (not observed and app.next_color()!='b'):
                self.last_sent=None;self.rejected=None
                next_color=getattr(self,'detected_turn',None) or ('b' if not observed else {'黑棋':'b','白棋':'w'}[self.import_turn.get()])
                # A generated but unconfirmed move must not change whose turn it is.
                if not forced and not getattr(self,'detected_turn',None) and observed and app.history and app.history[-1][1] not in observed and app.history[-1][1] in app.stones:
                    next_color=app.history[-1][0]
                app.import_camera(observed,next_color,keep_running=True)
                self.note.set(f'已自动接入 {len(observed)} 子，等待引擎同步完成。')
                return
        if app.ended():return
        if observed==app.stones:
            detected=getattr(self,'detected_turn',None)
            if detected and detected!=app.next_color():
                app.sync_camera_turn(detected)
                self.note.set('已识别当前轮次，正在同步引擎…');return
            self.resume_after_sync()
            self.rejected=None
            if app.next_color()==self.color():app.ai()
            else:self.note.set(f'局面一致，轮到{"黑棋" if app.next_color()=="b" else "白棋"}；AI 执{self.side.get()}，等待对方落子。')
            return
        vertex=candidate_move(app.stones,observed,app.next_color())
        signature=tuple(sorted(observed.items()))
        if not vertex:self.note.set('等待局面同步：请按 AI 坐标落子、完成提子，或校正识别。');return
        if self.rejected==signature:return
        self.rejected=signature
        self.note.set('识别到 '+vertex+'，正在检查合法局面…')
        app.play_camera(vertex,observed)
    def click_failed(self,vertex,error):
        self.output.set(False)
        self.waiting_manual=self.enabled.get()
        self.run_status.set('持续读盘中 · 等待目标局面同步')
        self.note.set(f'{vertex} 点击未确认：{error}。读盘继续；手动补下后会自动检测同步。')
    def resume_after_sync(self):
        if not self.waiting_manual:return
        self.waiting_manual=False
        if self.enabled.get() and self.run_mode.get()=='读盘并点击目标':
            self.output.set(True);self.arm_output()
        self.run_status.set('运行中：局面已追上，继续自动读盘')
    def on_ai(self,color,vertex,before):
        if not self.output.get():
            self.app.status.set(f'本地 AI 已生成 {vertex}；未点击野狐：自动点击开关未开启。');return
        if color!=self.color():
            self.app.status.set(f'本地 AI 已生成 {vertex}；未点击野狐：与设置的自动执子颜色不同。');return
        if self.output_busy:return
        signature=(len(self.app.history),color,vertex)
        if signature==self.last_sent:return
        self.last_sent=signature
        if not self.target or self.target.size!=self.app.board_size:
            self.pause();self.app.status.set('目标尚未定位或路数变化，未点击。');return
        target=self.target;token=threading.Event();self.output_cancel=token;self.output_busy=True
        self.note.set(f'正在向目标发送 {vertex}，视频持续读取中…')
        results=self.output_results
        def send():
            error=None
            try:target.click_move(color,vertex,before,cancel=token)
            except Exception as e:error=str(e)
            results.put((token,vertex,error))
        threading.Thread(target=send,daemon=True).start()
    def close(self):
        self.output_cancel.set()
        try:self.save_settings()
        except OSError:pass
        self.source_generation+=1
        self.closed=True;self.enabled.set(False);self.output.set(False);self.stop.set()
        self.window.after_cancel(self.timer);self.window.destroy()
        self.app.camera=None
