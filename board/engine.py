"""Local, serialized GTP bridge. KataGo owns the board and rule enforcement."""
from pathlib import Path
import queue
import re
import subprocess
import threading
import json
import os
import time

ROOT = Path(__file__).resolve().parent.parent
LETTERS = 'ABCDEFGHJKLMNOPQRST'

def vertex_xy(vertex, size=19):
    m = re.fullmatch(r'([A-HJ-T])(1[0-9]|[1-9])', vertex.upper())
    if not m or LETTERS.index(m[1]) >= size or int(m[2]) > size: raise ValueError('无效坐标')
    return LETTERS.index(m[1]), size-int(m[2])

def parse_board(text, size=19):
    board = {}
    rows = set()
    for line in text.splitlines():
        m = re.match(r'^\s*(\d{1,2})\s+(.*)$', line)
        if not m or not 1 <= int(m[1]) <= size: continue
        cells = re.findall(r'[.XO]', m[2])
        if len(cells) != size: raise RuntimeError('棋盘解析失败，已停止更新')
        rows.add(int(m[1]))
        for x, cell in enumerate(cells):
            if cell != '.': board[f'{LETTERS[x]}{m[1]}'] = 'b' if cell == 'X' else 'w'
    if len(rows) != size: raise RuntimeError('引擎未返回完整棋盘')
    return board

class Engine:
    def __init__(self,backend='gpu'):
        self.history = []
        self.setup_stones={};self.setup_next='b';self.turn_override=None
        self.size = 19
        self.serial = 0
        self.lock = threading.RLock()
        self.lines = queue.Queue()
        self.last_elapsed = 0.0
        if backend not in ('gpu','cpu'):raise ValueError('无效推理后端')
        runtime_file = ROOT/'board'/('runtime.cpu.json' if backend=='cpu' else 'runtime.json')
        if backend=='cpu' and not runtime_file.exists():raise RuntimeError('请先配置 KataGo CPU 引擎')
        runtime = json.loads(runtime_file.read_text(encoding='utf-8-sig')) if runtime_file.exists() else {}
        self.label = runtime.get('label', 'RTX 5080 · OpenCL')
        environment = os.environ.copy()
        environment['PATH'] = os.pathsep.join(runtime.get('dll_dirs', []) + [environment.get('PATH', '')])
        self.log = open(ROOT/'board'/'engine.log', 'a', encoding='utf-8')
        self.process = subprocess.Popen([
            runtime.get('executable', str(ROOT/'katago'/'katago.exe')), 'gtp', '-model',
            runtime.get('model', str(ROOT/'katago'/'default_model.bin.gz')), '-config',
            runtime.get('config', str(ROOT/'katago'/'fox_gtp.cfg'))], cwd=Path(runtime.get('executable',str(ROOT/'katago'/'katago.exe'))).parent, env=environment,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
            text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
        def pump():
            try:
                for line in self.process.stdout: self.lines.put(line)
            finally: self.lines.put(None)
        threading.Thread(target=pump, daemon=True).start()
        try:
            self.command('protocol_version')
            self.reset()
        except Exception:
            self.close()
            raise

    def command(self, command):
        with self.lock:
            if self.process.poll() is not None: raise RuntimeError('KataGo 已退出，请重新打开棋盘')
            self.serial += 1
            number = str(self.serial)
            self.process.stdin.write(number+' '+command+'\n')
            self.process.stdin.flush()
            response = []
            started = False
            try:
                while True:
                    line = self.lines.get(timeout=90)
                    if line is None: raise RuntimeError('引擎连接已断开，请重启棋盘')
                    line = line.rstrip('\r\n')
                    if not started:
                        if not line: continue
                        if not line.startswith(('=', '?')): continue
                        if not re.match(r'^[=?]'+number+r'(?:\s|$)', line):
                            raise RuntimeError('引擎响应序号不一致，请重启棋盘')
                        started = True
                    if not line: break
                    response.append(line)
            except queue.Empty:
                self.process.kill()
                raise RuntimeError('引擎响应超时，已停止进程，请重启棋盘')
            first = response[0]
            value = first[1+len(number):].strip()
            if first.startswith('?'): raise RuntimeError(value or '不合法的落子')
            return '\n'.join([value]+response[1:]).strip()

    def reset(self, size=19):
        if size not in (9, 13, 19):raise ValueError('支持 9、13、19 路棋盘')
        self.command('clear_board')
        self.command(f'boardsize {size}')
        self.command('komi 7.5')
        self.size = size
        self.history.clear()
        self.setup_stones={};self.setup_next='b';self.turn_override=None

    def import_position(self,stones,next_color):
        if next_color not in ('b','w'):raise ValueError('请选择轮到哪方')
        sgf=f'(;GM[1]FF[4]SZ[{self.size}]KM[7.5]RU[Chinese]PL[{next_color.upper()}]'
        for color in ('b','w'):
            points=[]
            for vertex,c in stones.items():
                if c not in ('b','w'):raise ValueError('无效棋子颜色')
                x,y=vertex_xy(vertex,self.size)
                if c==color:points.append('['+chr(97+x)+chr(97+y)+']')
            if points:sgf+='A'+color.upper()+''.join(points)
        path=ROOT/'board'/'import-position.sgf'
        path.write_text(sgf+')',encoding='utf-8')
        self.command('loadsgf '+path.as_posix())
        self.history.clear();self.setup_stones=dict(stones);self.setup_next=next_color;self.turn_override=None
        state=self.snapshot()
        if state['stones']!=stones:raise RuntimeError('引擎导入结果不一致，请重新导入')
        return state

    def play(self, color, vertex):
        if color not in ('b','w'): raise ValueError('无效颜色')
        vertex = vertex.lower() if vertex.lower() == 'pass' else vertex.upper()
        if vertex != 'pass': vertex_xy(vertex, self.size)
        self.command(f'play {color} {vertex}')
        self.history.append((color, vertex));self.turn_override=None

    def generate(self, color, seconds=2.0, visits=None):
        if color not in ('b','w'): raise ValueError('无效颜色')
        if not isinstance(seconds, (float, int)) or not 0.5 <= seconds <= 30:
            raise ValueError('思考时间必须在 0.5 到 30 秒之间')
        if visits is not None:
            if type(visits) is not int or not 1<=visits<=1000000:raise ValueError('搜索量必须是 1 到 1000000 的整数')
            self.command(f'kata-set-param maxVisits {visits}')
        self.command(f'kata-set-param maxTime {seconds}')
        started = time.perf_counter()
        vertex = self.command(f'genmove {color}').strip()
        self.last_elapsed = time.perf_counter() - started
        vertex = vertex.lower() if vertex.lower() in ('pass','resign') else vertex.upper()
        self.history.append((color, vertex));self.turn_override=None
        return vertex

    def play_observed(self, color, vertex, observed):
        self.play(color,vertex)
        try:
            state=self.snapshot()
            if state['stones']!=observed:
                raise RuntimeError('摄像头局面与合法落子结果不一致，已撤销本次识别')
            return state
        except Exception:
            self.undo()
            raise

    def undo(self):
        if not self.history: return
        if self.history[-1][1] != 'resign': self.command('undo')
        self.history.pop();self.turn_override=None

    def snapshot(self):
        return {'stones':parse_board(self.command('showboard'), self.size), 'history':list(self.history), 'size':self.size,'setup_stones':dict(self.setup_stones),'setup_next':self.setup_next,'turn_override':self.turn_override}

    def set_turn(self,color):
        if color not in ('b','w'):raise ValueError('无效轮次')
        self.turn_override=color
        return self.snapshot()

    def close(self):
        if getattr(self, 'process', None):
            if self.process.poll() is None:
                self.process.terminate()
                try: self.process.wait(timeout=3)
                except subprocess.TimeoutExpired: self.process.kill()
            for stream in (self.process.stdin, self.process.stdout):
                if stream:
                    try: stream.close()
                    except OSError: pass
        if getattr(self,'log',None): self.log.close()
