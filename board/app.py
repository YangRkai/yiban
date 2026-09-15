"""Manual intermediary board: Tk UI on main thread, serialized GTP on worker."""
import queue
import threading
import json
import uuid
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from engine import Engine, ROOT, LETTERS, vertex_xy
from difficulty import LEVELS,DEFAULT
from bundled_runtime import prepare_bundled_cpu
from coaching import LessonStore
from coach_ui import CoachWindow
from app_layout import build_layout

BG = '#f4f3ee'
INK = '#243c33'

class BoardApp:
    def __init__(self, root):
        prepare_bundled_cpu(ROOT)
        self.root = root
        self.engine = None
        self.camera = None
        self.lesson_store=LessonStore(ROOT/'board'/'learning')
        self.game_id=uuid.uuid4().hex
        self.coach_window=None
        self.recorded_player=None
        self.mode=tk.StringVar(value='本地 PVE');self.pve_running=True
        self.busy = False
        self.closed = False
        self.results = queue.Queue()
        self.stones = {}
        self.history = []
        self.setup_stones={};self.setup_next='b';self.turn_override=None
        self.board_size = 19
        self.size_choice = tk.StringVar(value='19 路')
        self.zoom = tk.DoubleVar(value=1.0)
        self.last_ai = None
        saved_side='白棋'
        try:
            value=json.loads((ROOT/'board'/'camera-settings.json').read_text(encoding='utf-8')).get('side')
            if value in ('黑棋','白棋'):saved_side=value
        except (OSError,ValueError,TypeError):pass
        self.ai_side = tk.StringVar(value=saved_side)
        self.difficulty=tk.StringVar(value=DEFAULT)
        self.auto = tk.BooleanVar(value=False)
        self.pending_vertex = None
        self.last_input_vertex = None
        self.reply_requested = False
        self.status = tk.StringVar(value='正在加载 KataGo…')
        self.turn = tk.StringVar(value='黑棋先行')
        self.bigmove = tk.StringVar(value='—')
        self.speed = tk.StringVar(value='均衡 · 2 秒')
        self.backend = tk.StringVar(value='正在连接引擎…')
        preferred='CPU' if (ROOT/'board'/'runtime.cpu.json').exists() and not (ROOT/'board'/'runtime.json').exists() else 'GPU'
        try:
            saved=json.loads((ROOT/'board'/'compute-settings.json').read_text(encoding='utf-8'))
            if saved.get('backend') in ('GPU','CPU') and (ROOT/'board'/('runtime.cpu.json' if saved['backend']=='CPU' else 'runtime.json')).exists():preferred=saved['backend']
        except (OSError,ValueError,TypeError):pass
        self.compute=tk.StringVar(value=preferred);self.active_compute=preferred
        build_layout(self)
        modebar=ttk.Frame(self.settings_host);modebar.pack(fill='x',padx=12,pady=4)
        ttk.Label(modebar,text='游戏模式').pack(side='left')
        modebox=ttk.Combobox(modebar,textvariable=self.mode,values=['本地 PVE','视频联动'],state='readonly',width=14);modebox.pack(side='left',padx=8);modebox.bind('<<ComboboxSelected>>',self.change_mode)
        ttk.Label(modebar,text='PVE：单击落子，电脑自动应手；AI 执黑时电脑先下。').pack(side='left')
        general=ttk.Frame(self.settings_host);general.pack(fill='x',padx=12,pady=4)
        ttk.Label(general,text='路数').pack(side='left')
        self.size_box=ttk.Combobox(general,textvariable=self.size_choice,values=['9 路','13 路','19 路'],width=7,state='readonly');self.size_box.pack(side='left',padx=8);self.size_box.bind('<<ComboboxSelected>>',self.change_size)
        ttk.Label(general,text='思考时间').pack(side='left')
        self.speed_box=ttk.Combobox(general,textvariable=self.speed,values=['极速 · 1 秒','均衡 · 2 秒','深思 · 8 秒'],width=15,state='readonly');self.speed_box.pack(side='left',padx=8)
        ttk.Label(general,textvariable=self.backend).pack(side='right')
        compute_bar=ttk.Frame(self.settings_host);compute_bar.pack(fill='x',padx=12,pady=4)
        ttk.Label(compute_bar,text='推理设备').pack(side='left')
        self.compute_box=ttk.Combobox(compute_bar,textvariable=self.compute,values=(['CPU','GPU'] if (ROOT/'board'/'runtime.json').exists() else ['CPU']),state='readonly',width=8);self.compute_box.pack(side='left',padx=8)
        self.compute_box.bind('<<ComboboxSelected>>',self.change_compute)
        ttk.Button(compute_bar,text='配置 CPU 引擎',command=self.configure_cpu).pack(side='left')
        self.moves=tk.Listbox(self.settings_host,height=3)
        self.camera_settings_host=ttk.Frame(self.settings_host)
        self.open_camera()
        recovery=tk.Frame(self.notice_host,bg=BG);self.recovery_bar=recovery;recovery.pack(fill='x',padx=16,pady=4)
        tk.Label(recovery,text='恢复时轮到',bg=BG,fg=INK).pack(side='left')
        ttk.Combobox(recovery,textvariable=self.camera.import_turn,values=['黑棋','白棋'],width=6,state='readonly').pack(side='left',padx=8)
        ttk.Button(recovery,text='重新读盘并继续',command=self.recover_game).pack(side='left')
        self.apply_mode_layout()
        root.protocol('WM_DELETE_WINDOW',self.close)
        self.poll_timer = root.after(80,self.poll)
        self.run(self.initialize, '正在加载引擎…', initialized=True)

    def record_learning(self, meta):
        if self.mode.get()!='本地 PVE':return
        if meta.get('new_pve'):
            self.game_id=uuid.uuid4().hex;self.recorded_player=None
        player='w' if self.ai_color()=='b' else 'b'
        if self.recorded_player and self.recorded_player!=player:
            return
        self.recorded_player=player
        state=dict(history=list(self.history),stones=dict(self.stones),size=self.board_size,
            setup_stones=dict(self.setup_stones),setup_next=self.setup_next)
        try:self.lesson_store.record(self.game_id,state,player)
        except OSError as exc:self.status.set('对局可继续，但自动记录失败：'+str(exc))

    def open_coach(self):
        if self.coach_window and not self.coach_window.closed:
            self.coach_window.window.lift();return
        if self.mode.get()!='本地 PVE':
            self.status.set('每局一题首版支持本地 PVE，请先切换到本地 PVE。');return
        self.record_learning({})
        game=self.lesson_store.read('game-'+self.game_id+'.json')
        self.coach_window=CoachWindow(self,self.lesson_store,game,ROOT)

    def initialize(self):
        config=ROOT/'board'/('runtime.cpu.json' if self.active_compute=='CPU' else 'runtime.json')
        if not config.exists():return None
        self.engine=Engine(backend=self.active_compute.lower())
        if self.closed:
            self.engine.close()
            return None
        return self.engine.snapshot()
    def configure_cpu(self):
        if self.busy:return
        paths={}
        for key,title in [('executable','选择 KataGo CPU 版可执行文件'),('model','选择 KataGo 模型'),('config','选择 CPU 版 GTP 配置')]:
            value=filedialog.askopenfilename(parent=self.root,title=title)
            if not value:return
            paths[key]=value
        paths.update(dll_dirs=[],label='KataGo · CPU')
        (ROOT/'board'/'runtime.cpu.json').write_text(json.dumps(paths,ensure_ascii=False,indent=2),encoding='utf-8')
        self.compute.set('CPU');self.change_compute()
    def change_compute(self,event=None):
        requested=self.compute.get()
        if self.busy or requested==self.active_compute:
            self.compute.set(self.active_compute);return
        if requested=='CPU' and not (ROOT/'board'/'runtime.cpu.json').exists():
            self.compute.set(self.active_compute);self.status.set('请点击“配置 CPU 引擎”，选择 CPU 版 KataGo、模型和 GTP 配置。');return
        self.stop_auto_game()
        stones=dict(self.stones);turn=self.next_color()
        def switch():
            replacement=Engine(backend=requested.lower())
            try:
                replacement.reset(self.board_size);replacement.import_position(stones,turn)
            except Exception:
                replacement.close();raise
            previous=self.engine;self.engine=replacement
            if previous:previous.close()
            return replacement.snapshot()
        self.run(switch,'正在切换到 '+requested+'…',compute=requested,clear=True)

    def next_color(self):
        if self.turn_override:return self.turn_override
        return ('w' if self.history[-1][0]=='b' else 'b') if self.history else self.setup_next

    def ended(self):
        return bool(self.history and (self.history[-1][1]=='resign' or (len(self.history)>1 and self.history[-1][1]==self.history[-2][1]=='pass')))

    def run(self,fn,label,**meta):
        if self.busy or self.closed:return
        meta['automation_epoch']=self.camera.automation_epoch if self.camera else None
        self.busy=True
        self.status.set(label)
        self.update_controls()
        def worker():
            try:self.results.put((fn(),None,meta))
            except Exception as e:self.results.put((None,str(e),meta))
        threading.Thread(target=worker,daemon=True).start()

    def poll(self):
        if self.closed:return
        try:
            state,error,meta=self.results.get_nowait()
            automation_current=not self.camera or meta.get('automation_epoch')==self.camera.automation_epoch
            self.busy=False
            if error:
                if meta.get('compute'):self.compute.set(self.active_compute)
                if meta.get('auto_import') and self.camera:self.camera.pause()
                self.pending_vertex=None
                self.reply_requested=False
                self.size_choice.set(f'{self.board_size} 路')
                self.status.set('操作失败：'+error)
                if not meta.get('camera') and not meta.get('auto_import'):messagebox.showerror('操作未完成',error,parent=self.root)
            elif state is not None:
                if meta.get('compute'):
                    self.active_compute=meta['compute']
                    (ROOT/'board'/'compute-settings.json').write_text(json.dumps({'backend':self.active_compute}),encoding='utf-8')
                self.stones=state['stones'];self.history=state['history']
                self.setup_stones=state.get('setup_stones',{});self.setup_next=state.get('setup_next','b');self.turn_override=state.get('turn_override')
                self.board_size=state['size']
                self.size_choice.set(f'{self.board_size} 路')
                self.backend.set(self.engine.label)
                if meta.get('ai'):
                    self.last_input_vertex=None
                    self.last_ai=self.history[-1][1]
                    self.bigmove.set({'pass':'PASS','resign':'认输'}.get(self.last_ai,self.last_ai))
                elif meta.get('clear'):
                    self.last_input_vertex=None
                    self.last_ai=None; self.bigmove.set('—')
                if self.ended():self.status.set('对局结束：AI 认输' if self.history[-1][1]=='resign' else '双方停一手，可保存棋谱。')
                elif meta.get('ai'):self.status.set(f'本地 AI 已生成 {self.last_ai} · 实际思考 {self.engine.last_elapsed:.2f} 秒 · {self.engine.label}')
                else:self.status.set('单击棋盘落子，电脑自动应手。' if self.mode.get()=='本地 PVE' else '单击落子 · 再点刚落下的棋子，AI 下下一手。')
                if meta.get('played'):
                    self.last_input_vertex=self.pending_vertex
                    self.pending_vertex=None
                self.refresh()
                self.record_learning(meta)
                if meta.get('camera') and self.camera and automation_current:
                    self.camera.resume_after_sync()
                if meta.get('ai') and self.camera and automation_current and self.mode.get()!='本地 PVE':
                    self.camera.on_ai(meta['ai_color'],self.last_ai,meta['before'])
            elif meta.get('initialized'):
                self.status.set('欢迎使用：请在设置中配置 KataGo 引擎。CPU 模式不需要显卡。')
                if self.settings_window.state()=='withdrawn':self.toggle_settings()
            self.update_controls()
            want_reply=self.auto.get() or self.reply_requested or meta.get('camera') or (self.camera and self.camera.should_reply())
            if not automation_current:want_reply=False
            if self.camera and (self.camera.enabled.get() or self.camera.output.get()):
                want_reply=want_reply and self.camera.color()==self.next_color()
            if self.mode.get()=='本地 PVE':
                want_reply=automation_current and self.pve_running and self.next_color()==self.ai_color()
            trigger=meta.get('played') or (self.mode.get()=='本地 PVE' and (meta.get('initialized') or meta.get('new_pve')))
            if not error and trigger and want_reply and not self.ended():
                self.reply_requested=False
                self.ai()
        except queue.Empty:pass
        self.poll_timer = self.root.after(80,self.poll)

    def update_controls(self):
        for b in self.buttons:b.configure(state='disabled' if self.busy or not self.engine else 'normal')
        self.color.configure(state='disabled' if self.busy else 'readonly')
        self.speed_box.configure(state='disabled' if self.busy else 'readonly')
        self.difficulty_box.configure(state='disabled' if self.busy else 'readonly')
        self.compute_box.configure(state='disabled' if self.busy else 'readonly')
        self.size_box.configure(state='disabled' if self.busy or not self.engine else 'readonly')

    def refresh(self):
        self.turn.set('对局结束' if self.ended() else ('轮到黑棋 ●' if self.next_color()=='b' else '轮到白棋 ○'))
        self.moves.delete(0,'end')
        for i,(c,v) in enumerate(self.history,1):self.moves.insert('end',f'{i:3}   {"黑" if c=="b" else "白"}   {v.upper()}')
        self.moves.see('end')
        self.draw()

    def geometry(self):
        w,h=self.canvas.winfo_width(),self.canvas.winfo_height()
        size=max(100,min(w,h)-70)*self.zoom.get()
        return (w-size)/2,(h-size)/2,size/(self.board_size-1)

    def draw(self):
        c=self.canvas;c.delete('all')
        x0,y0,s=self.geometry();r=(self.board_size-1)*s
        c.create_rectangle(x0-27,y0-27,x0+r+27,y0+r+27,fill='#dcb77b',outline='#c39b61',width=2)
        for i in range(self.board_size):
            c.create_line(x0+i*s,y0,x0+i*s,y0+r,fill='#735836')
            c.create_line(x0,y0+i*s,x0+r,y0+i*s,fill='#735836')
            for y in (y0-17,y0+r+17):c.create_text(x0+i*s,y,text=LETTERS[i],fill='#654d2f',font=('Consolas',10))
            for x in (x0-17,x0+r+17):c.create_text(x,y0+i*s,text=str(self.board_size-i),fill='#654d2f',font=('Consolas',10))
        stars={9:(2,4,6),13:(3,6,9),19:(3,9,15)}[self.board_size]
        for i in stars:
            for j in stars:
                if self.board_size != 19 and ((i==stars[1]) != (j==stars[1])):continue
                x,y=x0+i*s,y0+j*s;c.create_oval(x-3,y-3,x+3,y+3,fill='#634a2e',outline='')
        for vertex,color in self.stones.items():
            a,b=vertex_xy(vertex,self.board_size);x,y=x0+a*s,y0+b*s;rad=s*.455
            c.create_oval(x-rad+1,y-rad+2,x+rad+1,y+rad+2,fill='#b18f5b',outline='')
            c.create_oval(x-rad,y-rad,x+rad,y+rad,fill='#202522' if color=='b' else '#fafaf2',outline='#111813' if color=='b' else '#d0d1c5',width=1.2)
        if self.history and self.history[-1][1] in self.stones:
            a,b=vertex_xy(self.history[-1][1],self.board_size);x,y=x0+a*s,y0+b*s;rr=s*.14
            c.create_oval(x-rr,y-rr,x+rr,y+rr,outline='#e75939',width=2)

    def location(self,event):
        x0,y0,s=self.geometry();a=round((event.x-x0)/s);b=round((event.y-y0)/s)
        if not (0<=a<self.board_size and 0<=b<self.board_size):return None
        if abs(event.x-(x0+a*s))>s*.48 or abs(event.y-(y0+b*s))>s*.48:return None
        return a,b

    def hover(self,event):
        self.canvas.delete('hover')
        loc=self.location(event)
        if loc and not self.busy and not self.ended():
            a,b=loc;v=LETTERS[a]+str(self.board_size-b)
            if v not in self.stones:
                x0,y0,s=self.geometry();x,y=x0+a*s,y0+b*s
                self.canvas.create_oval(x-s*.4,y-s*.4,x+s*.4,y+s*.4,outline='#547061',width=2,tags='hover')

    def on_click(self,event):
        if self.mode.get()=='本地 PVE' and (not self.pve_running or self.next_color()==self.ai_color()):return
        if not self.engine or self.ended():return
        loc=self.location(event)
        if loc:
            vertex=LETTERS[loc[0]]+str(self.board_size-loc[1])
            if self.busy:
                if vertex==self.pending_vertex:self.reply_requested=True
                return
            if vertex in self.stones:
                if vertex==self.last_input_vertex and self.history and self.history[-1][1]==vertex:self.ai()
                return
            self.play(vertex)

    def play(self,vertex):
        if self.busy:return
        self.pending_vertex=vertex
        self.reply_requested=False
        color=self.next_color()
        def action():
            self.engine.play(color,vertex)
            return self.engine.snapshot()
        self.run(action,'正在录入 '+vertex+'…',played=True)

    def pass_move(self):
        if self.mode.get()=='本地 PVE' and (not self.pve_running or self.next_color()==self.ai_color()):return
        if not self.ended():self.play('pass')

    def ai(self):
        if self.ended() or self.busy:return
        if self.mode.get()=='本地 PVE' and self.next_color()!=self.ai_color():return
        color=self.next_color()
        before=dict(self.stones)
        seconds={'极速 · 1 秒':1.0,'均衡 · 2 秒':2.0,'深思 · 8 秒':8.0}[self.speed.get()]
        visits=LEVELS[self.difficulty.get()]
        def action():
            self.engine.generate(color, seconds=seconds,visits=visits)
            return self.engine.snapshot()
        self.run(action,f'{self.active_compute} 正在思考 · 目标 {seconds:g} 秒…',ai=True,ai_color=color,before=before)

    def ai_color(self):return 'b' if self.ai_side.get()=='黑棋' else 'w'
    def apply_mode_layout(self):
        pve=self.mode.get()=='本地 PVE'
        if pve:
            if str(self.video_host) in self.body.panes():self.body.forget(self.video_host)
            self.camera_settings_host.pack_forget();self.recovery_bar.pack_forget()
            self.camera.notice.pack_forget()
        else:
            if str(self.video_host) not in self.body.panes():self.body.insert(0,self.video_host,weight=1)
            self.camera_settings_host.pack(fill='x')
            self.recovery_bar.pack(fill='x',padx=16,pady=4)
            self.camera.notice.pack(fill='x',padx=8,pady=4)
        self.start_auto_button.configure(text='继续对弈' if pve else '▶ 开始自动')
    def change_mode(self,event=None):
        self.stop_auto_game();self.apply_mode_layout()
        if self.mode.get()=='本地 PVE':
            self.camera.stop.set();self.pve_running=True
            if self.engine and not self.busy and self.next_color()==self.ai_color() and not self.ended():self.ai()
        else:
            self.camera.start()
    def toggle_settings(self):
        if self.settings_window.state()!='withdrawn':self.settings_window.withdraw()
        else:self.settings_window.deiconify();self.settings_window.lift()

    def open_camera(self):
        if self.camera:return
        from camera_panel import CameraPanel
        self.camera=CameraPanel(self)

    def start_auto_game(self):
        if self.mode.get()=='本地 PVE':
            self.pve_running=True
            if self.engine and not self.busy and not self.ended() and self.next_color()==self.ai_color():self.ai()
            self.status.set('PVE 进行中：轮到你时单击棋盘落子。');return
        if self.busy or not self.engine:return
        if not self.camera:self.open_camera()
        self.camera.run_mode.set('读盘并点击目标')
        self.camera.start_auto()
        self.status.set(self.camera.run_status.get())
        if not self.camera.enabled.get() or not self.camera.output.get():
            if self.settings_window.state()=='withdrawn':self.toggle_settings()

    def stop_auto_game(self):
        self.pve_running=False
        self.auto.set(False);self.reply_requested=False
        if self.camera:self.camera.pause()
        self.status.set('自动下棋已停止。')
    def recover_game(self):
        if not self.engine:return
        self.auto.set(False);self.reply_requested=False
        self.camera.recover_current()
        self.status.set('正在从视频恢复当前棋盘；无需重开一局。')

    def play_camera(self,vertex,observed):
        if self.busy or self.ended():return
        color=self.next_color()
        self.pending_vertex=vertex
        self.reply_requested=False
        def action():return self.engine.play_observed(color,vertex,observed)
        self.run(action,'摄像头识别 '+vertex+' · 正在校验局面…',played=True,camera=True)

    def import_camera(self,stones,next_color,keep_running=False):
        if self.busy or not self.engine:return
        if self.camera and not keep_running:self.camera.pause()
        self.auto.set(False);self.reply_requested=False;self.pending_vertex=None
        self.run(lambda:self.engine.import_position(stones,next_color),'正在自动同步局面…' if keep_running else '正在导入识别局面…',clear=True,auto_import=keep_running)

    def sync_camera_turn(self,color):
        if not self.busy:self.run(lambda:self.engine.set_turn(color),'正在同步当前轮次…')

    def undo(self):
        if not self.history:return
        if self.camera:self.camera.pause()
        count=2 if self.mode.get()=='本地 PVE' and len(self.history)>=2 and self.history[-1][0]==self.ai_color() else 1
        def action():
            for _ in range(count):self.engine.undo()
            return self.engine.snapshot()
        self.run(action,'正在悔棋…',clear=True)

    def new_game(self):
        if self.busy or not self.engine:return
        self.auto.set(False);self.reply_requested=False;self.pending_vertex=None
        if self.camera:self.camera.reset_for_new_game()
        def action():
            previous=self.engine.snapshot()
            if previous['stones'] or previous['history']:
                folder=ROOT/'board'/'game-backups';folder.mkdir(exist_ok=True)
                path=folder/(datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.json')
                path.write_text(json.dumps(previous,ensure_ascii=False,indent=2),encoding='utf-8')
            self.engine.reset(self.board_size)
            return self.engine.snapshot()
        self.pve_running=True
        self.run(action,'正在创建新对局…',clear=True,new_pve=True)

    def change_size(self,event=None):
        size=int(self.size_choice.get().split()[0])
        if size==self.board_size:return
        if self.busy or not self.engine:
            self.size_choice.set(f'{self.board_size} 路')
            return
        if (self.stones or self.history) and not messagebox.askyesno('切换棋盘',f'切换为 {size} 路将开启新局。继续吗？\n显示缩放不需要清空棋盘。',parent=self.root):
            self.size_choice.set(f'{self.board_size} 路')
            return
        if self.camera:self.camera.pause()
        def action():
            self.engine.reset(size)
            return self.engine.snapshot()
        self.run(action,f'正在切换到 {size} 路…',clear=True,new_pve=True)

    def save(self):
        path=filedialog.asksaveasfilename(parent=self.root,title='保存棋谱',defaultextension='.sgf',filetypes=[('SGF 棋谱','*.sgf')],initialfile='KataGo-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.sgf')
        if not path:return
        sgf=f'(;GM[1]FF[4]CA[UTF-8]SZ[{self.board_size}]KM[7.5]RU[Chinese]AP[YiBan:1.0]'
        sgf+='PL['+self.setup_next.upper()+']'
        for color in ('b','w'):
            points=[]
            for vertex,c in self.setup_stones.items():
                if c==color:
                    x,y=vertex_xy(vertex,self.board_size);points.append('['+chr(97+x)+chr(97+y)+']')
            if points:sgf+='A'+color.upper()+''.join(points)
        for color,vertex in self.history:
            if vertex=='resign':continue
            if vertex=='pass':point=''
            else:
                x,y=vertex_xy(vertex,self.board_size);point=chr(97+x)+chr(97+y)
            sgf+=';'+color.upper()+'['+point+']'
        try:
            with open(path,'w',encoding='utf-8') as f:f.write(sgf+')')
            self.status.set('棋谱已保存：'+path)
        except OSError as e:messagebox.showerror('保存失败',str(e),parent=self.root)

    def close(self):
        if self.coach_window and not self.coach_window.closed:self.coach_window.close()
        self.closed=True
        if self.camera:self.camera.close()
        self.root.after_cancel(self.poll_timer)
        if self.engine:self.engine.close()
        self.root.destroy()

if __name__=='__main__':
    import sys
    import ctypes
    try:ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError,OSError):pass
    root=tk.Tk()
    app=BoardApp(root)
    if '--camera' in sys.argv:root.after(300,app.open_camera)
    root.mainloop()
