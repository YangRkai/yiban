"""Locate an axis-aligned screen Go grid by its regularly spaced long lines."""
import numpy as np
from vision import cv2

def _lattice(profile,size):
    indices=np.flatnonzero(profile>max(12,float(profile.max())*.2))
    groups=np.split(indices,np.flatnonzero(np.diff(indices)>1)+1)
    peaks=np.array([float(np.mean(g)) for g in groups if len(g)],dtype=float)
    best=None
    for a in peaks:
        for b in peaks:
            step=(b-a)/(size-1)
            if step<8:continue
            positions=a+np.arange(size)*step
            errors=np.min(abs(positions[:,None]-peaks),axis=1)
            if np.max(errors)>max(2,step*.13):continue
            score=(b-a)-float(errors.sum())*3
            if best is None or score>best[0]:best=(score,a,b)
    if best is None:raise ValueError('未找到完整等距棋盘线，请让 OBS 显示完整棋盘，或使用手动四角定位')
    return best[1:]

def locate_board(frame,size):
    gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
    mask=cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY_INV,31,9)
    h,w=gray.shape
    # Exclude window chrome: its horizontal border can mimic an extra grid row.
    hsv=cv2.cvtColor(frame,cv2.COLOR_BGR2HSV)
    wood=cv2.inRange(hsv,np.array([8,40,90]),np.array([42,255,255]))
    wood=cv2.morphologyEx(wood,cv2.MORPH_CLOSE,np.ones((9,9),np.uint8))
    contours,_=cv2.findContours(wood,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        contour=max(contours,key=cv2.contourArea)
        if cv2.contourArea(contour)>h*w*.08:
            x,y,bw,bh=cv2.boundingRect(contour)
            region=np.zeros_like(mask);region[y:y+bh,x:x+bw]=255
            mask=cv2.bitwise_and(mask,region)
    horizontal=cv2.morphologyEx(mask,cv2.MORPH_OPEN,np.ones((1,max(30,w//6)),np.uint8))
    top,bottom=_lattice(np.sum(horizontal>0,axis=1),size)
    strip=mask[max(0,round(top)):min(h,round(bottom)+1)]
    vertical=cv2.morphologyEx(strip,cv2.MORPH_OPEN,np.ones((max(30,strip.shape[0]//3),1),np.uint8))
    left,right=_lattice(np.sum(vertical>0,axis=0),size)
    # Refit horizontal lines using only the chosen grid width.
    top,bottom=_lattice(np.sum(horizontal[:,round(left):round(right)+1]>0,axis=1),size)
    if not .7<(right-left)/(bottom-top)<1.4:raise ValueError('棋盘比例异常，请调整 OBS 画面或手动定位')
    return [(left,top),(right,top),(right,bottom),(left,bottom)]
