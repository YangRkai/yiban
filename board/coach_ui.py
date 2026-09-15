"""A separate practice board never mutates the live game."""
import json
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog
import zipfile
from engine import LETTERS, vertex_xy
from coach_analysis import analyze_game
from coaching import game_sgf
from coach_layout import build_coach_layout


class CoachWindow:
    def __init__(self, app, store, game, root_path):
        self.app=app;self.store=store;self.game=game;self.root_path=root_path
        self.lesson=None;self.revealed=False;self.submitted=False;self.selection=None
        self.cancel=threading.Event();self.events=queue.Queue();self.closed=False
        self.window=tk.Toplevel(app.root);self.window.title('每局一题 · 独立重试与复测')
        self.message=tk.StringVar(value='分析所选对局，或取一道到期的原题复测。复测不等于已学会迁移。')
        build_coach_layout(self)
        self.saved_games={}
        if game:self.saved_games['打开窗口时的本局']=game
        for path in sorted(store.folder.glob('game-*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:50]:
            saved=store.read(path.name)
            if saved and saved.get('history'):
                self.saved_games[f"{saved['game_id'][:8]} · {len(saved['history'])} 手 · {saved['size']} 路"]=saved
        self.game_choice.configure(values=list(self.saved_games))
        if self.saved_games:self.game_choice.current(0)
        self.game_choice.bind('<<ComboboxSelected>>',self.select_game)
        self.canvas.bind('<Configure>',lambda e:self.draw());self.canvas.bind('<Button-1>',self.choose)
        self.branch_box.bind('<<ComboboxSelected>>',lambda e:self.reset_frames())
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        self.timer=self.window.after(100,self.poll);self.controls(False)
    def controls(self, ready):
        for button in (self.submit,self.reveal):button.configure(state='normal' if ready else 'disabled')
        for button in (self.previous,self.next):button.configure(state='normal' if ready and self.revealed else 'disabled')
    def analyze(self):
        if self.lesson:return
        if not self.game or not self.game['history']:
            self.message.set('先下一局，再来找一个值得练习的问题。');return
        existing=self.store.read('lesson-'+self.game['game_id']+'.json')
        if existing:self.load(existing);return
        self.analyze_button.configure(state='disabled');self.review_button.configure(state='disabled')
        self.game_choice.configure(state='disabled')
        def work():
            try:
                lesson=analyze_game(self.root_path,self.game,self.cancel,lambda x:self.events.put(('progress',x)))
                self.events.put(('done',lesson))
            except Exception as exc:self.events.put(('error',str(exc)))
        threading.Thread(target=work,daemon=True).start()
    def poll(self):
        if self.closed:return
        try:
            while True:
                kind,value=self.events.get_nowait()
                if kind=='progress':self.message.set(value)
                elif kind=='done':
                    self.game_choice.configure(state='readonly')
                    self.review_button.configure(state='normal')
                    if value:self.load(self.store.save_lesson(value))
                    else:
                        self.analyze_button.configure(state='normal')
                        self.message.set('本次有限搜索没有找到复核一致的题目。这不代表本局没有失误。')
                else:
                    self.game_choice.configure(state='readonly')
                    self.message.set('教学分析未完成：'+value)
                    self.analyze_button.configure(state='normal');self.review_button.configure(state='normal')
        except queue.Empty:pass
        self.timer=self.window.after(100,self.poll)
    def select_game(self,event=None):
        self.game=self.saved_games[self.game_choice.get()];self.lesson=None;self.revealed=False
        self.analyze_button.configure(state='normal');self.review_button.configure(state='normal')
        self.controls(False);self.branch_box.configure(state='disabled');self.draw()
        self.message.set('已选择记录的对局。点击“分析本局”寻找一个可以复核的问题。')
    def load(self, lesson):
        self.lesson=lesson;self.revealed=False;self.submitted=False;self.selection=None
        self.frames=lesson['recommended_frames'];self.index=0
        self.branch.set('建议变化');self.branch_box.configure(state='disabled')
        self.analyze_button.configure(state='disabled');self.review_button.configure(state='disabled')
        color='黑' if lesson['player_color']=='b' else '白'
        self.message.set(f"第 {lesson['move_number']} 手，轮到你执{color}。先在棋盘选择下法，再提交；答案暂不显示。")
        self.controls(True);self.draw()
    def review(self):
        lesson=self.store.due()
        if lesson:self.load(lesson)
        else:self.message.set('暂无到期题目。首次练习后至少隔 24 小时再做原题复测；不把记住答案算作迁移能力。')
    def geometry(self):
        size=self.lesson['size'];w=self.canvas.winfo_width();h=self.canvas.winfo_height()
        spacing=max(1,(min(w,h)-60)/(size-1));return (w-spacing*(size-1))/2,(h-spacing*(size-1))/2,spacing
    def draw(self):
        self.canvas.delete('all')
        if not self.lesson:
            self.canvas.create_text(self.canvas.winfo_width()/2,self.canvas.winfo_height()/2,
                text='选择一局棋，点击右侧“分析所选对局”\n找到可复核的问题后，棋盘会显示在这里。',
                fill='#665333',font=('Microsoft YaHei UI',11),justify='center',width=max(100,self.canvas.winfo_width()-40))
            return
        n=self.lesson['size'];x,y,s=self.geometry()
        for i in range(n):
            self.canvas.create_line(x,y+i*s,x+(n-1)*s,y+i*s,fill='#665333')
            self.canvas.create_line(x+i*s,y,x+i*s,y+(n-1)*s,fill='#665333')
            self.canvas.create_text(x+i*s,y-16,text=LETTERS[i]);self.canvas.create_text(x-18,y+i*s,text=n-i)
        for v,c in self.frames[self.index].items():
            a,b=vertex_xy(v,n);cx=x+a*s;cy=y+b*s;r=s*.44
            self.canvas.create_oval(cx-r,cy-r,cx+r,cy+r,fill='#202522' if c=='b' else '#fffdf5',outline='#555')
        if self.selection and not self.revealed:
            a,b=vertex_xy(self.selection,n);cx=x+a*s;cy=y+b*s
            self.canvas.create_oval(cx-s*.35,cy-s*.35,cx+s*.35,cy+s*.35,outline='#187bca',width=3)
    def choose(self,event):
        if not self.lesson or self.revealed or self.submitted:return
        x,y,s=self.geometry();a=round((event.x-x)/s);b=round((event.y-y)/s);n=self.lesson['size']
        if 0<=a<n and 0<=b<n:
            v=LETTERS[a]+str(n-b)
            if v not in self.frames[0]:self.selection=v;self.draw()
    def answer(self):
        if not self.selection or self.submitted:return
        matched=self.selection==self.lesson['recommended_move'];self.submitted=True
        self.store.attempt(self.lesson['game_id'],self.selection,matched,self.revealed)
        self.submit.configure(state='disabled')
        self.message.set('已记录：独立重试选中了参考点。不代表已经掌握，请以后复测。' if matched else
            '已记录你的选择；与本题参考点不同，不直接判为错误。点击“看建议与变化”比较。')
    def show_answer(self):
        if not self.lesson:return
        if not self.submitted:
            self.store.attempt(self.lesson['game_id'],None,False,True);self.submitted=True
        self.revealed=True;self.controls(True);self.submit.configure(state='disabled');self.branch_box.configure(state='readonly')
        self.reset_frames()
    def reset_frames(self):
        if not self.revealed:return
        self.frames=self.lesson['recommended_frames' if self.branch.get()=='建议变化' else 'actual_frames'];self.index=0;self.draw();self.explain()
    def explain(self):
        l=self.lesson
        pv=l['recommended_pv' if self.branch.get()=='建议变化' else 'actual_pv']
        self.message.set(f"实战 {l['actual_move']}；参考 {l['recommended_move']}。两档搜索均估计参考下法至少好约 {l['loss_points']} 目。"
            f"\n{self.branch.get()}：{' → '.join(pv)}（当前 {self.index}/{len(self.frames)-1}）。这是模拟应对，不是必然发生。"
            '\n练习：逐手看对方如何应对，再比较两条变化。具体棋理原因尚未验证，不作推断。')
    def step(self,delta):
        if not self.revealed:return
        self.index=max(0,min(len(self.frames)-1,self.index+delta));self.draw();self.explain()
    def export(self):
        filename=filedialog.asksaveasfilename(parent=self.window,defaultextension='.zip',initialfile='弈伴复盘.zip',filetypes=[('ZIP','*.zip')])
        if not filename:return
        lessons=self.store.lessons()
        selected={l['game_id'] for l in lessons}
        games=[l.get('game_snapshot',self.store.read('game-'+l['game_id']+'.json')) for l in lessons]
        prompt=self.root_path/'AI复盘提示词.md'
        text=prompt.read_text(encoding='utf-8') if prompt.exists() else '只依据附件证据讲解围棋。引用对局与手数；缺乏证据时说明不能判断。不要编造棋理、变化或个人习惯。原题复测不是掌握证明。'
        try:
            with zipfile.ZipFile(filename,'w',zipfile.ZIP_DEFLATED) as z:
                z.writestr('AI复盘提示词.md',text)
                z.writestr('manifest.json',json.dumps(dict(schema_version='0.1',scope='本机全部已生成教学题目；单人使用',lesson_count=len(lessons)),ensure_ascii=False))
                z.writestr('analysis.json',json.dumps(lessons,ensure_ascii=False,indent=2))
                z.writestr('games.json',json.dumps(games,ensure_ascii=False,indent=2))
                for game in games:
                    if game:z.writestr('games/'+game['game_id']+'.sgf',game_sgf(game))
                z.writestr('review.md',text+'\n\n## 分析证据与尝试记录\n```json\n'+json.dumps(lessons,ensure_ascii=False,indent=2)+'\n```')
            self.message.set('已导出本机教学记录，不含截图或账号。请自行上传给 AI；ZIP 不支持时可解压上传 review.md。')
        except OSError as exc:self.message.set('导出失败：'+str(exc))
    def close(self):
        self.cancel.set();self.closed=True;self.window.after_cancel(self.timer);self.window.destroy()
