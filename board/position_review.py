"""Frozen recognition result that the user can correct before importing."""
import tkinter as tk
from tkinter import ttk
from PIL import Image,ImageTk
from engine import LETTERS,vertex_xy
from vision import cv2

class PositionReview:
    def __init__(self,parent,reader,frame,reading,next_color,submit):
        self.window=tk.Toplevel(parent);self.window.title('核对并修正局面')
        self.stones=dict(reading.stones);self.uncertain=set(reading.uncertain)
        self.empty=set()
        self.size=reader.size;self.submit=submit;self.margin=reader.margin;self.step=reader.step
        self.mode=tk.StringVar(value='黑棋');self.turn=tk.StringVar(value='黑棋' if next_color=='b' else '白棋')
        ttk.Label(self.window,text='画面已冻结。选择黑棋 / 白棋 / 空点，再点击交叉点修正；橙框为不确定位置。').pack(padx=10,pady=8)
        bar=ttk.Frame(self.window);bar.pack(fill='x',padx=10)
        for label in ('黑棋','白棋','空点'):
            ttk.Radiobutton(bar,text=label,variable=self.mode,value=label).pack(side='left',padx=5)
        ttk.Button(bar,text='其余不确定点设为空',command=self.clear_uncertain).pack(side='left',padx=12)
        self.canvas=tk.Canvas(self.window,width=reader.edge+1,height=reader.edge+1,highlightthickness=0)
        self.canvas.pack(padx=10,pady=8)
        self.photo=ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(reader.warp(frame),cv2.COLOR_BGR2RGB)))
        self.canvas.bind('<Button-1>',self.click)
        self.status=tk.StringVar();ttk.Label(self.window,textvariable=self.status).pack()
        bottom=ttk.Frame(self.window);bottom.pack(fill='x',padx=10,pady=10)
        ttk.Label(bottom,text='当前轮到').pack(side='left')
        ttk.Combobox(bottom,textvariable=self.turn,values=['黑棋','白棋'],state='readonly',width=6).pack(side='left',padx=8)
        self.confirm=ttk.Button(bottom,text='确认局面并导入',command=self.accept);self.confirm.pack(side='right')
        ttk.Button(bottom,text='取消',command=self.window.destroy).pack(side='right',padx=8)
        self.draw()
    def click(self,event):
        x=round((event.x-self.margin)/self.step);y=round((event.y-self.margin)/self.step)
        if not (0<=x<self.size and 0<=y<self.size):return
        vertex=LETTERS[x]+str(self.size-y)
        color={'黑棋':'b','白棋':'w','空点':None}[self.mode.get()]
        if color:self.stones[vertex]=color;self.empty.discard(vertex)
        else:self.stones.pop(vertex,None);self.empty.add(vertex)
        self.uncertain.discard(vertex);self.draw()
    def clear_uncertain(self):
        for vertex in self.uncertain:self.stones.pop(vertex,None);self.empty.add(vertex)
        self.uncertain.clear();self.draw()
    def draw(self):
        self.canvas.delete('all');self.canvas.create_image(0,0,image=self.photo,anchor='nw')
        for vertex in self.empty:
            x,y=vertex_xy(vertex,self.size);x=self.margin+x*self.step;y=self.margin+y*self.step
            self.canvas.create_rectangle(x-10,y-10,x+10,y+10,fill='#e3be7e',outline='#00bb55')
            self.canvas.create_text(x,y,text='空',fill='#205030')
        for vertex,color in self.stones.items():
            x,y=vertex_xy(vertex,self.size);x=self.margin+x*self.step;y=self.margin+y*self.step
            self.canvas.create_oval(x-11,y-11,x+11,y+11,fill='#202020' if color=='b' else 'white',outline='#00bb55',width=2)
        for vertex in self.uncertain:
            x,y=vertex_xy(vertex,self.size);x=self.margin+x*self.step;y=self.margin+y*self.step
            self.canvas.create_rectangle(x-13,y-13,x+13,y+13,outline='#ff7700',width=2)
        self.status.set(f'黑 {list(self.stones.values()).count("b")} 子 / 白 {list(self.stones.values()).count("w")} 子 / 待处理 {len(self.uncertain)} 处')
        self.confirm.configure(state='disabled' if self.uncertain else 'normal')
    def accept(self):
        if self.uncertain:return
        if self.submit(dict(self.stones),{'黑棋':'b','白棋':'w'}[self.turn.get()]) is not False:
            self.window.destroy()
