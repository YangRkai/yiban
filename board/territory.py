"""Provisional Chinese area ownership. Never adjudicates a finished game."""
import math
from engine import LETTERS


class PressToggle:
    def __init__(self):
        self.visible=False
        self.started=None
        self.held=False

    def press(self, now):
        if self.started is None:self.started=now;self.held=False

    def tick(self, now):
        if self.started is not None and now-self.started>=.35:
            self.held=True;self.visible=True

    def release(self, now):
        if self.started is None:return
        self.visible=False if self.held or now-self.started>=.35 else not self.visible
        self.started=None;self.held=False

    def cancel(self):
        if self.started is not None:self.visible=False
        self.started=None;self.held=False


def position_key(state):
    return (state.get('game_id'),state['size'],tuple(sorted(state['stones'].items())),
            tuple(tuple(m) for m in state['history']),tuple(sorted(state.get('setup_stones',{}).items())),
            state.get('setup_next','b'),state['next_color'],state.get('turn_override'))


def analysis_position(state):
    game=dict(state)
    game['history']=[m for m in state['history'] if m[1]!='resign']
    # A manually overridden turn cannot be expressed by the original alternating history.
    if state.get('turn_override'):
        game.update(history=[],setup_stones=dict(state['stones']),setup_next=state['next_color'])
    return game


def summarize(size, stones, ownership, lead):
    if len(ownership)!=size*size or not math.isfinite(lead):raise ValueError('归属估算数据不完整')
    result={c:dict(stones=0,empty=0,dead=0,total=0) for c in ('b','w')}
    result.update(marks={},uncertain=0,lead=lead)
    for index,value in enumerate(ownership):
        if not math.isfinite(value) or not -1<=value<=1:raise ValueError('归属估算数据无效')
        vertex=LETTERS[index%size]+str(size-index//size)
        owner='b' if value>=.65 else 'w' if value<=-.65 else '?'
        result['marks'][vertex]=owner
        if owner=='?':result['uncertain']+=1;continue
        category='empty' if vertex not in stones else 'stones' if stones[vertex]==owner else 'dead'
        result[owner][category]+=1;result[owner]['total']+=1
    return result


def estimate(root, state, cancel):
    from coach_analysis import Analysis
    game=analysis_position(state)
    engine=Analysis(root,cancel,purpose='territory')
    try:
        data=engine.query(game,game['history'],state['next_color'],32,ownership=True)
        return summarize(state['size'],state['stones'],data['ownership'],data['rootInfo']['scoreLead'])
    finally:engine.close()


def summary_text(result):
    parts=[]
    for color,name in (('b','黑'),('w','白')):
        r=result[color]
        parts.append(f"{name}归属 {r['total']} 点＝本方子 {r['stones']}＋空点 {r['empty']}＋疑似对方死子 {r['dead']}")
    lead=result['lead']
    advantage=f"{'黑' if lead>=0 else '白'}领先约 {abs(lead):.1f} 目"
    parts.append(f"未确定 {result['uncertain']} 点（灰色）· 中国规则，白贴 7.5 目 · 引擎估算：{advantage}")
    parts.append('归属标记为估算，标记点数不直接判胜负；终局也需确认死活。')
    return '\n'.join(parts)
