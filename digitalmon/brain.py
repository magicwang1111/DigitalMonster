"""One persistent, small adaptive companion network; original implementation."""
import math
import random
import time

ACTIONS = ('observe','ask_food','seek_touch','rest')

def ensure(state):
    if 'brain' not in state:
        state['brain']={'id':state['id'], 'weights':[[0.0]*4 for _ in range(5)],
            'needs':[0.4,0.4,0.4,0.0], 'updates':0,'steps':0,'action':'observe',
            'probabilities':[.25]*4,'inputs':[1,.4,.4,.4,0], 'last_feedback':None}
    return state['brain']

def forward(brain):
    x=[1]+brain['needs']
    logits=[sum(x[i]*brain['weights'][i][a] for i in range(5)) for a in range(4)]
    values=[math.exp(v-max(logits)) for v in logits]
    return x,[v/sum(values) for v in values]

def tick(store):
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        s=store._state(c)
        if s['paused'] or s['stopped']:return False
        b=ensure(s)
        b['needs']=[min(1,b['needs'][0]+.0005), min(1,b['needs'][1]+.0003),
                    min(1,b['needs'][2]+.0002), min(1,b['needs'][3]+.0001)]
        x,p=forward(b)
        rng=random.Random(str(b['steps'])+s['id'])
        a=rng.choices(range(4),weights=p)[0]
        b.update(action=ACTIONS[a],inputs=x,probabilities=p,steps=b['steps']+1)
        if a==3:b['needs'][3]=max(0,b['needs'][3]-.001)
        s['ticks']+=1
        s['name']='基尔兽'
        store._save(c,s)
        if b['steps']%10==0:store._event(c,'brain_action',{'brain_id':b['id'],'action':b['action'],'probabilities':p})
    return True

def feedback(store,action):
    target={'feed':1,'pet':2,'play':0}[action]
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        s=store._state(c); b=ensure(s)
        x,p=forward(b)
        before=[row[:] for row in b['weights']]
        for i in range(5):
            for a in range(4):
                b['weights'][i][a]=max(-4,min(4,b['weights'][i][a]+.04*x[i]*((1 if a==target else 0)-p[a])))
        b['needs'][0 if action=='feed' else 1 if action=='pet' else 2]*=.45
        b['updates']+=1
        b['last_feedback']={'action':action,'time':time.time(),
            'method':'caregiver-supervised association; not autonomous reward discovery'}
        store._save(c,s)
        store._event(c,'brain_learning',{'brain_id':b['id'],'cause':action,'update':b['updates'],
            'weights_before':before,'weights_after':b['weights']})
