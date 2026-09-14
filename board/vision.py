"""Calibrated screen-board recognition; no camera or desktop access on import."""
from pathlib import Path
import sys
from dataclasses import dataclass, field
sys.path.insert(0,str(Path(__file__).resolve().parent/'vendor'))
import cv2
import numpy as np
from engine import LETTERS

@dataclass
class Reading:
    stones: dict
    unknown: int
    image: object
    uncertain: set = field(default_factory=set)
    last_move: str | None = None

class BoardVision:
    def __init__(self,size,corners,empty_frame):
        if size not in (9,13,19):raise ValueError('棋盘只支持 9/13/19 路')
        self.size=size
        self.step=32;self.margin=20
        self.edge=(size-1)*self.step+2*self.margin
        p=np.asarray(corners,dtype=np.float32)
        if p.shape!=(4,2) or not cv2.isContourConvex(p.reshape(-1,1,2)) or abs(cv2.contourArea(p))<1000:
            raise ValueError('请按左上、右上、右下、左下选择四个最外侧交叉点')
        m=self.margin;e=self.edge-m
        self.matrix=cv2.getPerspectiveTransform(p,np.float32([[m,m],[e,m],[e,e],[m,e]]))
        self.reference=self.warp(empty_frame)
        self.gray=cv2.cvtColor(self.reference,cv2.COLOR_BGR2GRAY).astype(np.float32)
        if not 45 < float(np.median(self.gray)) < 253 or float(np.std(self.gray)) < 2:
            raise ValueError('画面无信号、过暗或缺少棋盘纹理；请接好输入，并使用明亮的空棋盘重新标定')
        yy,xx=np.mgrid[-16:17,-16:17];rr=np.sqrt(xx*xx+yy*yy)
        self.core=rr<=9
        self.color_core=self.core & ~((xx>=0)&(yy>=0))
        self.ring=(rr>=15)&(rr<=16)
        self.surround=rr>=20
        self.marker_core=(xx>=2)&(yy>=2)&(xx<=9)&(yy<=9)&(xx+yy<=12)
    def warp(self,frame):
        return cv2.warpPerspective(frame,self.matrix,(self.edge+1,self.edge+1))
    def read(self,frame):
        warped=self.warp(frame)
        valid=cv2.warpPerspective(np.ones(frame.shape[:2],np.uint8),self.matrix,(self.edge+1,self.edge+1),flags=cv2.INTER_NEAREST)>0
        gray=cv2.cvtColor(warped,cv2.COLOR_BGR2GRAY).astype(np.float32)
        saturation=cv2.cvtColor(warped,cv2.COLOR_BGR2HSV)[:,:,1]
        board_saturation=float(np.median(saturation))
        background=float(np.median(gray))
        drift=float(np.median(gray-self.gray))
        if abs(drift)>28:return Reading({},self.size*self.size,warped,{LETTERS[x]+str(self.size-y) for y in range(self.size) for x in range(self.size)})
        delta=gray-self.gray-drift
        stones={};unknown=0;uncertain=set();markers=[]
        for y in range(self.size):
            for x in range(self.size):
                vertex=LETTERS[x]+str(self.size-y)
                cx=self.margin+x*self.step;cy=self.margin+y*self.step
                patch=delta[cy-16:cy+17,cx-16:cx+17]
                available=valid[cy-16:cy+17,cx-16:cx+17]
                color_mask=self.color_core & available
                if np.count_nonzero(color_mask)<30:color_mask=self.core & available
                surround_mask=self.surround & available
                if np.count_nonzero(color_mask)<20:
                    unknown+=1;uncertain.add(vertex);continue
                core=patch[self.core & available];ring=patch[surround_mask]
                absolute=gray[cy-16:cy+17,cx-16:cx+17][color_mask]
                sat=saturation[cy-16:cy+17,cx-16:cx+17][color_mask]
                neutral_white=board_saturation>45 and np.mean((sat<min(40,board_saturation*.5)) & (absolute>145))>.7
                d=float(np.median(core))
                bad_ring=len(ring)>0 and np.mean(np.abs(ring)>28)>.4
                surround_gray=gray[cy-16:cy+17,cx-16:cx+17][surround_mask]
                if len(surround_gray) and np.median(surround_gray)>np.median(absolute)+35:bad_ring=False
                if bad_ring:
                    unknown+=1;uncertain.add(vertex);continue
                color=None
                if np.median(absolute)<background-35 and np.mean(absolute<background-25)>.55:color='b'
                elif neutral_white or (np.median(absolute)>background+22 and np.mean(absolute>background+16)>.7):color='w'
                elif np.mean(np.abs(absolute-background)>25)>.3 and abs(float(np.median(absolute))-background)>15:
                    unknown+=1;uncertain.add(vertex);continue
                if color:
                    stones[LETTERS[x]+str(self.size-y)]=color
                    marker=gray[cy-16:cy+17,cx-16:cx+17][self.marker_core & available]
                    if len(marker)>10 and ((color=='b' and np.mean(marker>140)>.4) or (color=='w' and np.mean(marker<90)>.4)):
                        markers.append(vertex)
                    cv2.circle(warped,(cx,cy),12,(0,210,0),1)
        return Reading(stones,unknown,warped,uncertain,markers[0] if len(markers)==1 else None)

class StableBoard:
    def __init__(self,seconds=.6):self.seconds=seconds;self.key=None;self.since=0
    def update(self,stones,unknown,now):
        if unknown:self.key=None;return None
        key=tuple(sorted(stones.items()))
        if key!=self.key:self.key=key;self.since=now;return None
        return dict(key) if now-self.since>=self.seconds else None

class TemporalBoard:
    """Use two recent agreeing observations per point; expire unresolved points."""
    def __init__(self,size,max_age=.45):
        self.vertices=[LETTERS[x]+str(size-y) for y in range(size) for x in range(size)]
        self.max_age=max_age;self.points={};self.last_frame=None
    def update(self,reading,now,frame_id=None):
        fresh=frame_id is None or frame_id!=self.last_frame
        self.last_frame=frame_id
        unresolved=set();stones={}
        for vertex in self.vertices:
            if fresh and vertex not in reading.uncertain:
                value=reading.stones.get(vertex)
                old=self.points.get(vertex)
                count=old[1]+1 if old and old[0]==value and now-old[2]<=self.max_age else 1
                self.points[vertex]=(value,count,now)
            point=self.points.get(vertex)
            if not point or point[1]<2 or now-point[2]>self.max_age:unresolved.add(vertex)
            elif point[0]:stones[vertex]=point[0]
        return Reading(stones,len(unresolved),reading.image,unresolved,reading.last_move)


def candidate_move(expected,observed,color):
    added=[v for v,c in observed.items() if v not in expected]
    if len(added)!=1 or observed[added[0]]!=color:return None
    for v,c in expected.items():
        if v in observed and observed[v]!=c:return None
        if v not in observed and c==color:return None
    return added[0]
