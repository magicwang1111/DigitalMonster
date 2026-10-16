"""Run a real trained planner for the companion's interactive bread-search task."""
import hashlib
import json
from pathlib import Path


class LivePlanner:
    def __init__(self, data):
        self.data = Path(data)
        self.loaded = None

    def play(self, seed, goal=None):
        import torch
        from .maze import generate, MOVES
        from .maze_train import make_model, tensors
        if type(seed) is not int or not 0 <= seed <= 100000000:
            raise ValueError('invalid scene seed')
        if self.loaded is None:
            candidates=[]
            for path in (self.data/'research').glob('*/report.json'):
                report=json.loads(path.read_text())
                if report.get('size')==21 and report.get('status')=='completed':
                    candidates.append((report.get('best_validation_success',0),-report['width'],path,report))
            if not candidates:
                raise ValueError('no completed 21x21 checkpoint available')
            _,_,path,r=sorted(candidates,key=lambda row:row[:2],reverse=True)[0]
            checkpoint=path.parent/'best.pt'
            digest=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
            if digest!=r['checkpoint_sha256']:
                raise ValueError('checkpoint hash mismatch')
            torch.set_num_threads(2)
            model=make_model(torch,width=r['width'],rounds=r['rounds'])
            model.load_state_dict(torch.load(checkpoint,map_location='cpu',weights_only=True))
            model.eval()
            self.loaded=(model,digest,path.parent.name)
        model,digest,run=self.loaded
        maze=generate(seed,size=21)
        if goal is not None:
            if not isinstance(goal,list) or len(goal)!=2 or any(type(v) is not int or not 0<=v<21 for v in goal):
                raise ValueError('invalid bread position')
            if maze['walls'][goal[1]][goal[0]]:
                raise ValueError('bread cannot be placed inside an obstacle')
            maze['goal']=tuple(goal)
        with torch.inference_mode():
            observation,_=tensors(torch,[maze],'cpu')
            actions=model(observation)[0].argmax(0).tolist()
        x,y=maze['start']; path=[[x,y]]; seen=set()
        while (x,y)!=tuple(maze['goal']) and len(path)<150 and (x,y) not in seen:
            seen.add((x,y)); dx,dy=MOVES[actions[y][x]]
            nx,ny=x+dx,y+dy
            if not 0<=nx<21 or not 0<=ny<21 or maze['walls'][ny][nx]:
                break
            x,y=nx,ny; path.append([x,y])
        return {'seed':seed,'walls':maze['walls'],'goal':maze['goal'],'path':path,
                'success':(x,y)==tuple(maze['goal']),'model_run':run,'checkpoint_sha256':digest,
                'controller':'trained neural planner; CPU inference; no shortest-path fallback'}
