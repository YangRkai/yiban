"""Native Tk layout adapted from the YiBan Figma composition."""
import tkinter as tk
from tkinter import ttk
from difficulty import LEVELS

BG='#f4f3ee'
INK='#243c33'
MUTED='#768179'
PAPER='#ffffff'
TINT='#e7ede5'


def build_layout(app):
    root=app.root
    root.title('弈伴 · 对弈与练习');root.geometry('1380x900');root.minsize(1050,720);root.configure(bg=BG)
    style=ttk.Style(root);style.theme_use('clam')
    style.configure('TFrame',background=BG)
    style.configure('TLabel',background=BG,foreground=INK,font=('Microsoft YaHei UI',10))
    style.configure('TButton',font=('Microsoft YaHei UI',10),padding=(10,7),background='#f5f6f2',foreground=INK,borderwidth=1,relief='flat')
    style.map('TButton',background=[('active','#e7ede5')],foreground=[('disabled','#9ca59e')])
    style.configure('Primary.TButton',background=INK,foreground='white',borderwidth=0,padding=(12,9))
    style.map('Primary.TButton',background=[('disabled','#bdc8be'),('active','#375849')],foreground=[('disabled','#f3f5f1')])
    style.configure('TCombobox',font=('Microsoft YaHei UI',10),padding=5,fieldbackground='#f5f6f2',foreground=INK)
    header=tk.Frame(root,bg=BG);header.pack(fill='x',padx=26,pady=(18,14))
    tk.Label(header,text='弈伴',font=('Microsoft YaHei UI',25,'bold'),bg=BG,fg=INK).pack(side='left')
    tk.Label(header,text='下一局棋，学会一个新思路',font=('Microsoft YaHei UI',10),bg=BG,fg=MUTED).pack(side='left',padx=20)
    ttk.Button(header,text='设置',command=app.toggle_settings,width=9).pack(side='right')
    app.notice_host=tk.Frame(root,bg=BG);app.notice_host.pack(fill='x',padx=24)
    app.main_notice=tk.Label(app.notice_host,textvariable=app.status,bg=TINT,fg=INK,font=('Microsoft YaHei UI',10),anchor='w',justify='left',padx=16,pady=10)
    app.main_notice.pack(fill='x')
    app.main_notice.bind('<Configure>',lambda e:app.main_notice.configure(wraplength=max(200,e.width-32)))
    workspace=tk.Frame(root,bg=BG);workspace.pack(fill='both',expand=True,padx=24,pady=(16,20))
    workspace.columnconfigure(0,weight=1);workspace.columnconfigure(1,weight=0,minsize=300);workspace.rowconfigure(0,weight=1)
    app.body=ttk.Panedwindow(workspace,orient='horizontal');app.body.grid(row=0,column=0,sticky='nsew',padx=(0,18))
    app.video_host=tk.Frame(app.body,bg=PAPER);app.board_host=tk.Frame(app.body,bg=PAPER)
    app.body.add(app.board_host,weight=1)
    tk.Label(app.video_host,text='实时视频棋盘',font=('Microsoft YaHei UI',12,'bold'),bg=PAPER,fg=INK).pack(anchor='w',padx=16,pady=14)
    board_header=tk.Frame(app.board_host,bg=PAPER);board_header.pack(fill='x',padx=18,pady=(16,6))
    tk.Label(board_header,textvariable=app.mode,bg=PAPER,fg=INK,font=('Microsoft YaHei UI',12,'bold')).pack(side='left')
    tk.Label(board_header,textvariable=app.bigmove,bg=PAPER,fg=INK,font=('Consolas',16,'bold')).pack(side='right',padx=12)
    tk.Label(board_header,textvariable=app.turn,bg=PAPER,fg=MUTED,font=('Microsoft YaHei UI',10)).pack(side='right')
    tk.Label(app.board_host,text='棋谱自动保存在本机 · 下完后，挑一道题再练一次',bg=PAPER,fg=MUTED,font=('Microsoft YaHei UI',9)).pack(side='bottom',anchor='w',padx=18,pady=(8,16))
    app.canvas=tk.Canvas(app.board_host,bg=PAPER,highlightthickness=0);app.canvas.pack(fill='both',expand=True,padx=8)
    app.canvas.bind('<Configure>',lambda e:app.draw());app.canvas.bind('<Button-1>',app.on_click)
    app.canvas.bind('<Motion>',app.hover);app.canvas.bind('<Leave>',lambda e:app.canvas.delete('hover'))
    sidebar=tk.Frame(workspace,bg=BG,width=300);sidebar.grid(row=0,column=1,sticky='nsew')
    app.footer=tk.Frame(sidebar,bg=PAPER,padx=18,pady=16);app.footer.pack(fill='x')
    tk.Label(app.footer,text='这一局',font=('Microsoft YaHei UI',16,'bold'),bg=PAPER,fg=INK).pack(anchor='w',pady=(0,12))
    for label,variable,values,attr in [('AI 执子',app.ai_side,['黑棋','白棋'],'color'),('难度',app.difficulty,list(LEVELS),'difficulty_box')]:
        row=tk.Frame(app.footer,bg=PAPER);row.pack(fill='x',pady=(0,9))
        tk.Label(row,text=label,bg=PAPER,fg=MUTED,font=('Microsoft YaHei UI',10),width=7,anchor='w').pack(side='left')
        field=ttk.Combobox(row,textvariable=variable,values=values,state='readonly',width=12);field.pack(side='right');setattr(app,attr,field)
    app.start_auto_button=ttk.Button(app.footer,text='开始 / 继续',style='Primary.TButton',command=app.start_auto_game)
    app.start_auto_button.pack(fill='x',pady=(3,9));app.buttons=[app.start_auto_button]
    pair=tk.Frame(app.footer,bg=PAPER);pair.pack(fill='x',pady=(0,9));pair.columnconfigure((0,1),weight=1)
    for i,(label,action) in enumerate([('悔棋',app.undo),('停一手',app.pass_move)]):
        b=ttk.Button(pair,text=label,command=action,width=9);b.grid(row=0,column=i,sticky='ew',padx=(0,5) if i==0 else (5,0));app.buttons.append(b)
    b=ttk.Button(app.footer,text='新开一局',command=app.new_game);b.pack(fill='x',pady=(0,9));app.buttons.append(b)
    pair=tk.Frame(app.footer,bg=PAPER);pair.pack(fill='x',pady=(0,8));pair.columnconfigure((0,1),weight=1)
    ttk.Button(pair,text='停止（F8）',command=app.stop_auto_game,width=9).grid(row=0,column=0,sticky='ew',padx=(0,5))
    b=ttk.Button(pair,text='保存棋谱',command=app.save,width=9);b.grid(row=0,column=1,sticky='ew',padx=(5,0));app.buttons.append(b)
    app.ai_button=ttk.Button(app.footer,text='让 AI 下这一手',command=app.ai);app.ai_button.pack(fill='x');app.buttons.append(app.ai_button)
    lesson=tk.Frame(sidebar,bg=TINT,padx=18,pady=16);lesson.pack(fill='x',pady=(14,0))
    tk.Label(lesson,text='每局一题',font=('Microsoft YaHei UI',15,'bold'),bg=TINT,fg=INK).pack(anchor='w')
    tk.Label(lesson,text='先自己重试，再看建议变化。',font=('Microsoft YaHei UI',9),bg=TINT,fg=MUTED).pack(anchor='w',pady=(6,10))
    app.lesson_button=ttk.Button(lesson,text='复盘 / 隔日复测',style='Primary.TButton',command=app.open_coach);app.lesson_button.pack(fill='x')
    app.settings_window=tk.Toplevel(root);app.settings_window.title('弈伴 · 设置');app.settings_window.geometry('980x650');app.settings_window.withdraw()
    app.settings_window.protocol('WM_DELETE_WINDOW',app.settings_window.withdraw)
    scroller=tk.Canvas(app.settings_window,bg=BG,highlightthickness=0);scroll=ttk.Scrollbar(app.settings_window,command=scroller.yview)
    scroll.pack(side='right',fill='y');scroller.pack(fill='both',expand=True);scroller.configure(yscrollcommand=scroll.set)
    app.settings_host=ttk.Frame(scroller);item=scroller.create_window(0,0,window=app.settings_host,anchor='nw')
    app.settings_host.bind('<Configure>',lambda e:scroller.configure(scrollregion=scroller.bbox('all')))
    scroller.bind('<Configure>',lambda e:scroller.itemconfigure(item,width=e.width))

