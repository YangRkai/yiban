"""User-selected desktop board output. Only called after explicit UI arming."""
import ctypes
from ctypes import wintypes
import time
import re
import numpy as np
from PIL import ImageGrab
from vision import cv2, BoardVision
from engine import vertex_xy

user32=ctypes.windll.user32
user32.GetForegroundWindow.restype=wintypes.HWND
user32.GetAncestor.argtypes=[wintypes.HWND,wintypes.UINT]
user32.GetAncestor.restype=wintypes.HWND
user32.WindowFromPoint.argtypes=[wintypes.POINT]
user32.WindowFromPoint.restype=wintypes.HWND
user32.IsWindow.argtypes=[wintypes.HWND]
user32.GetClientRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
user32.ClientToScreen.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.POINT)]
user32.SetForegroundWindow.argtypes=[wintypes.HWND]
user32.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowTextLengthW.argtypes=[wintypes.HWND]
user32.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
user32.IsWindowVisible.argtypes=[wintypes.HWND]
user32.IsIconic.argtypes=[wintypes.HWND]


def windows():
    found=[]
    callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    def visit(hwnd,param):
        length=user32.GetWindowTextLengthW(hwnd)
        if length and user32.IsWindowVisible(hwnd):
            buf=ctypes.create_unicode_buffer(length+1)
            user32.GetWindowTextW(hwnd,buf,length+1)
            if not any(x in buf.value for x in ('弈伴','ChatGPT','Codex')):
                found.append((int(hwnd),buf.value))
        return True
    user32.EnumWindows(callback(visit),0)
    return found


def identity(hwnd):
    if not user32.IsWindow(hwnd):raise RuntimeError('目标窗口已关闭，请重新选择')
    pid=wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
    return pid.value


def client_box(hwnd):
    rect=wintypes.RECT();point=wintypes.POINT(0,0)
    if not user32.GetClientRect(hwnd,ctypes.byref(rect)) or not user32.ClientToScreen(hwnd,ctypes.byref(point)):
        raise RuntimeError('无法读取目标窗口坐标')
    return (point.x,point.y,rect.right,rect.bottom)

def same_board_window_title(original,current):
    """Fox embeds turn counts and game status in an otherwise stable room title."""
    if original==current:return True
    def room(title):
        match=re.search(r'(\d+)\s*号?房间',title)
        return match.group(1) if match else None
    original_room=room(original)
    return original_room is not None and original_room==room(current)

class WindowBoard:
    def __init__(self,hwnd,title):
        self.hwnd=hwnd;self.title=title;self.pid=identity(hwnd);self.reader=None
        self.dimensions=None;self.corners=None;self.size=None
    def turn_hint(self):
        if identity(self.hwnd)!=self.pid:return None
        title=ctypes.create_unicode_buffer(1024);user32.GetWindowTextW(self.hwnd,title,1024)
        if not same_board_window_title(self.title,title.value) or '对局结束' in title.value:return None
        match=re.search(r'第\s*(\d+)\s*手',title.value)
        return ('w' if int(match.group(1))%2 else 'b') if match else None
    def capture(self):
        if identity(self.hwnd)!=self.pid:raise RuntimeError('目标窗口进程已变化，请重新标定')
        title=ctypes.create_unicode_buffer(1024)
        user32.GetWindowTextW(self.hwnd,title,1024)
        if not same_board_window_title(self.title,title.value):
            raise RuntimeError('目标已切换到其他房间或页面，请重新选择目标棋盘')
        if user32.IsIconic(self.hwnd):raise RuntimeError('请先还原目标棋盘窗口')
        user32.SetForegroundWindow(self.hwnd)
        time.sleep(.15)
        if user32.GetForegroundWindow()!=self.hwnd:raise RuntimeError('无法激活目标棋盘；请手动把它切到前台后重试')
        x,y,w,h=client_box(self.hwnd)
        if w<100 or h<100:raise RuntimeError('目标窗口太小')
        pixels=np.array(ImageGrab.grab(bbox=(x,y,x+w,y+h),all_screens=True))
        return cv2.cvtColor(pixels,cv2.COLOR_RGB2BGR)
    def calibrate(self,size,corners,empty):
        self.reader=BoardVision(size,corners,empty)
        self.corners=np.asarray(corners,np.float32)
        self.size=size;self.dimensions=(empty.shape[1],empty.shape[0])
    def click_move(self,color,vertex,expected,cancel=None):
        if not self.reader:raise RuntimeError('目标棋盘还没有标定')
        if vertex.lower() in ('pass','resign'):raise RuntimeError('AI 停一手或认输，请手动操作对应按钮')
        if cancel is not None and cancel.is_set():raise RuntimeError('自动已停止')
        frame=self.capture()
        if (frame.shape[1],frame.shape[0])!=self.dimensions:raise RuntimeError('目标窗口尺寸已变化，请重新标定')
        reading=self.reader.read(frame)
        if reading.unknown or reading.stones!=expected:
            raise RuntimeError(f'点击前校验未通过：目标识别 {len(reading.stones)} 子、不确定 {reading.unknown} 处；引擎 {len(expected)} 子')
        a,b=vertex_xy(vertex,self.size)
        matrix=cv2.getPerspectiveTransform(np.float32([[0,0],[self.size-1,0],[self.size-1,self.size-1],[0,self.size-1]]),self.corners)
        point=cv2.perspectiveTransform(np.float32([[[a,b]]]),matrix)[0,0]
        ox,oy,w,h=client_box(self.hwnd)
        if (w,h)!=self.dimensions:raise RuntimeError('目标尺寸变化')
        x,y=ox+round(float(point[0])),oy+round(float(point[1]))
        if user32.GetForegroundWindow()!=self.hwnd:raise RuntimeError('目标窗口失去焦点，未点击')
        owner=user32.GetAncestor(user32.WindowFromPoint(wintypes.POINT(x,y)),2)
        if owner!=self.hwnd:raise RuntimeError('落子位置被其他窗口遮挡，未点击')
        if user32.GetAsyncKeyState(0x77):raise RuntimeError('已按 F8 暂停，未点击')
        if cancel is not None and cancel.is_set():raise RuntimeError('自动已停止，未点击')
        user32.SetCursorPos(x,y)
        user32.mouse_event(2,0,0,0,0)
        try:time.sleep(.08)
        finally:user32.mouse_event(4,0,0,0,0)
        # Sending input is not an acknowledgement from the target application.
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            if cancel is not None and cancel.is_set():raise RuntimeError('自动已停止')
            time.sleep(.15)
            current=self.capture()
            if (current.shape[1],current.shape[0])!=self.dimensions:
                raise RuntimeError('点击后窗口尺寸变化，无法确认落子')
            result=self.reader.read(current)
            if vertex not in result.uncertain and result.stones.get(vertex)==color:return
        raise RuntimeError(f'已发送 {vertex} 点击，但目标未识别到该棋子；请检查野狐是否轮到你、是否要求双击，或画面识别是否正确')
