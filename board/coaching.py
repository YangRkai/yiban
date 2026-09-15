"""Local lesson evidence and history. No natural-language diagnosis is invented."""
import json
import math
import os
import time
from pathlib import Path


def game_sgf(game):
    from engine import vertex_xy
    sgf=f"(;GM[1]FF[4]CA[UTF-8]SZ[{game['size']}]KM[7.5]RU[Chinese]"
    for color,move in game['history']:
        if move=='resign':break
        if move=='pass':point=''
        else:
            x,y=vertex_xy(move,game['size']);point=chr(97+x)+chr(97+y)
        sgf+=';'+color.upper()+'['+point+']'
    return sgf+')'


def verified_gap(color, pairs):
    gaps = [(a-b)*(1 if color == 'b' else -1) for a,b in pairs]
    if len(gaps) < 2 or not all(math.isfinite(x) for x in gaps): return None
    if min(gaps) < 2 or max(gaps)-min(gaps) > max(2, min(gaps)*.5): return None
    return round(min(gaps), 2)


class LessonStore:
    def __init__(self, folder):
        self.folder=Path(folder); self.folder.mkdir(parents=True,exist_ok=True)
    def read(self, name, default=None):
        try:return json.loads((self.folder/name).read_text(encoding='utf-8'))
        except (OSError,ValueError):return default
    def write(self, name, data):
        target=self.folder/name; temp=target.with_suffix('.tmp')
        temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        os.replace(temp,target)
    def record(self, game_id, state, player):
        data=dict(state, game_id=game_id,player_color=player, rules='chinese',komi=7.5)
        self.write('game-'+game_id+'.json',data);return data
    def lessons(self):
        return [v for p in self.folder.glob('lesson-*.json') if (v:=self.read(p.name))]
    def save_lesson(self, lesson):
        name='lesson-'+lesson['game_id']+'.json';old=self.read(name,{})
        if old:return old
        lesson=dict(lesson,attempts=old.get('attempts',[]),created_at=old.get('created_at',time.time()))
        self.write(name,lesson);return lesson
    def attempt(self, game_id, move, matched, revealed, now=None):
        name='lesson-'+game_id+'.json';lesson=self.read(name)
        lesson['attempts'].append(dict(at=time.time() if now is None else now,move=move,
            matched_recommendation=matched,answer_seen=revealed))
        self.write(name,lesson)
    def due(self, now=None):
        now=time.time() if now is None else now
        candidates=[]
        for lesson in self.lessons():
            attempts=lesson.get('attempts',[])
            if attempts and now-attempts[-1]['at']>=86400:candidates.append(lesson)
        return min(candidates,key=lambda x:x['attempts'][-1]['at']) if candidates else None
