"""Independent CPU analysis; GTP validates all displayed PV positions."""
import json
import hashlib
import queue
import subprocess
import threading
import time
from pathlib import Path
from engine import Engine
from coaching import verified_gap


class Analysis:
    def __init__(self, root, cancel, purpose='coach'):
        self.cancel=cancel;self.root=root
        runtime=json.loads((root/'board/runtime.cpu.json').read_text(encoding='utf-8-sig'))
        self.model=runtime['model'];self.lines=queue.Queue()
        config=root/'board'/f'{purpose}-analysis.cfg'
        config.write_text('numAnalysisThreads = 1\nnumSearchThreads = 2\nmaxVisits = 32\nreportAnalysisWinratesAs = BLACK\nanalysisPVLen = 6\nlogToStderr = false\n',encoding='utf-8')
        self.log=open(root/'board'/f'{purpose}-analysis.log','a',encoding='utf-8')
        self.process=subprocess.Popen([runtime['executable'],'analysis','-model',runtime['model'],'-config',str(config)],
            cwd=Path(runtime['executable']).parent,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,
            text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
        def pump():
            for line in self.process.stdout:self.lines.put(line)
            self.lines.put(None)
        threading.Thread(target=pump,daemon=True).start()
        self.serial=0
    def query(self, game, moves, color, visits, allowed=None, ownership=False):
        if self.cancel.is_set():raise RuntimeError('分析已取消')
        self.serial+=1
        request=dict(id=str(self.serial),moves=moves,initialPlayer='B',rules='chinese',komi=7.5,
            boardXSize=game['size'],boardYSize=game['size'],maxVisits=visits,
            overrideSettings=dict(reportAnalysisWinratesAs='BLACK',wideRootNoise=0.0))
        if allowed:request['allowMoves']=[dict(player=color.upper(),moves=[allowed],untilDepth=1)]
        if ownership:
            request['includeOwnership']=True
            request['initialPlayer']=game.get('setup_next','b').upper()
            request['initialStones']=[[c.upper(),v] for v,c in game.get('setup_stones',{}).items()]
        self.process.stdin.write(json.dumps(request)+'\n');self.process.stdin.flush()
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            if self.cancel.is_set():raise RuntimeError('分析已取消')
            try:line=self.lines.get(timeout=.15)
            except queue.Empty:continue
            if line is None:raise RuntimeError('教学引擎退出，请查看 coach-analysis.log')
            result=json.loads(line)
            if result.get('id')!=request['id']:continue
            if 'error' in result:raise RuntimeError(result['error'])
            if not result.get('isDuringSearch',False) and 'moveInfos' in result:return result
        raise RuntimeError('教学分析超时')
    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
        self.process.stdin.close();self.process.stdout.close();self.log.close()


def analyze_game(root, game, cancel, progress):
    if game.get('setup_stones') or game.get('setup_next','b')!='b':
        raise RuntimeError('首版教学仅支持从空盘开始的普通 PVE 对局')
    engine=Analysis(root,cancel)
    try:
        history=[m for m in game['history'] if m[1]!='resign']
        candidates=[];player=game['player_color']
        for i,(color,actual) in enumerate(history):
            if cancel.is_set():raise RuntimeError('分析已取消')
            if color!=player or actual=='pass':continue
            progress(f'筛查第 {i+1} 手 / 共 {len(history)} 手；可随时取消')
            before=engine.query(game,history[:i],color,16)
            info=min(before['moveInfos'],key=lambda x:x['order'])
            if info['move']==actual or info['move']=='pass':continue
            after=engine.query(game,history[:i+1],'w' if color=='b' else 'b',16)
            gap=(info['scoreLead']-after['rootInfo']['scoreLead'])*(1 if player=='b' else -1)
            candidates.append((gap,i,info['move']))
        # Screening is approximate: inspect at most three candidates, never claim global worst.
        for _,i,recommended in sorted(candidates,reverse=True)[:3]:
            pairs=[];evidence=[];actual=history[i][1]
            progress(f'复核第 {i+1} 手：分别比较实战与建议下法')
            for visits in (64,128):
                a=engine.query(game,history[:i],player,visits,recommended)
                b=engine.query(game,history[:i],player,visits,actual)
                ai=next(x for x in a['moveInfos'] if x['move']==recommended)
                bi=next(x for x in b['moveInfos'] if x['move']==actual)
                pairs.append((ai['scoreLead'],bi['scoreLead']))
                evidence.append(dict(budget=visits,recommended=ai,actual=bi))
            gap=verified_gap(player,pairs)
            if gap is None:continue
            progress('核对变化合法性，准备棋盘演示')
            board=Engine(backend='cpu')
            try:
                engine_version=board.command('version')
                def frames(pv):
                    board.reset(game['size'])
                    for c,v in history[:i]:board.play(c,v)
                    result=[board.snapshot()['stones']];c=player
                    for v in pv[:6]:
                        if cancel.is_set():raise RuntimeError('分析已取消')
                        board.play(c,v);result.append(board.snapshot()['stones']);c='w' if c=='b' else 'b'
                    return result
                good=evidence[-1]['recommended']['pv'][:6];bad=evidence[-1]['actual']['pv'][:6]
                good_frames=frames(good);bad_frames=frames(bad)
            finally:board.close()
            return dict(game_id=game['game_id'],move_number=i+1,player_color=player,size=game['size'],
                actual_move=actual,recommended_move=recommended,loss_points=gap,evidence=evidence,
                recommended_pv=good,actual_pv=bad,recommended_frames=good_frames,actual_frames=bad_frames,
                score_perspective='BLACK',analysis_visits=[64,128],model_sha256=hashlib.sha256(Path(engine.model).read_bytes()).hexdigest(),
                engine_version=engine_version,game_snapshot=game,
                position_history=history[:i],rules='chinese',komi=7.5,
                limitation='有限 CPU 搜索的候选比较；不是唯一正确下法，不证明具体棋理原因。')
        return None
    finally:engine.close()
