"""Companion presentation. Simulated bonding is separate from measured learning."""
import json
import time
from pathlib import Path

FORMS = ['基尔兽', '古拉兽', '大古拉兽', '红莲骑士兽']


def stage_for(state, reports):
    p,b=state.get('pet',{}),state.get('brain',{})
    sources=len(set(b.get('explored_sources',[])))
    stage=0
    for level,feeds,touches,updates,steps,reads in ((1,10,10,30,1200,3),(2,30,30,100,7200,6),(3,80,80,250,21600,10)):
        if (p.get('feed_count',0)>=feeds and p.get('touch_count',0)>=touches and
            b.get('updates',0)>=updates and b.get('steps',0)>=steps and sources>=reads):stage=level
    return stage


def status(store, data):
    state = store.snapshot()
    reports = []
    for path in (Path(data)/'research').glob('*/report.json'):
        if path.stat().st_size > 2*1024**2:
            continue
        try:
            reports.append(json.loads(path.read_text(encoding='utf-8')))
        except (ValueError, OSError):
            pass
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        current = store._state(c)
        pet = current.setdefault('pet', {'bond': 0, 'interactions': 0, 'stage': 0, 'last_action': None})
        candidate = stage_for(current, [])
        if candidate > pet['stage'] and not current['paused'] and not current['stopped']:
            pet['stage'] = candidate
            store._event(c, 'digivolution', {'stage': candidate, 'form': FORMS[candidate],
                                             'reason': 'care/exploration game milestones; same brain identity retained'})
        store._save(c, current)
        return {**pet, 'form': FORMS[pet['stage']], 'name': '基尔兽', 'brain': current.get('brain', {}),
                'simulated': True, 'forms': FORMS,
                'progress': {'feeds':pet.get('feed_count',0),'touches':pet.get('touch_count',0),
                    'learning_updates':current.get('brain',{}).get('updates',0),
                    'active_steps':current.get('brain',{}).get('steps',0),
                    'unique_sources':len(set(current.get('brain',{}).get('explored_sources',[])))},
                'requirements': ['基尔兽：初始形态',
                    '古拉兽：喂食10次、摸摸10次、学习30次、活动1200步、探索3个来源',
                    '大古拉兽：喂食30次、摸摸30次、学习100次、活动7200步、探索6个来源',
                    '红莲骑士兽：喂食80次、摸摸80次、学习250次、活动21600步、探索10个来源',
                    'CM / X 抗体：后续形态，目前尚未开放'],
                'capability_note': '亲密度与外观是模拟状态；不代表意识。当前语言回复为规则回执。'}


def interact(store, action):
    replies = {'pet': '摸摸已收到，陪伴记录保存了。', 'feed': '收到一份数字食物，模拟能量恢复了。',
               'play': '一起玩的时刻已经记下来了。'}
    if action not in replies:
        raise ValueError('unknown interaction')
    from .brain import feedback
    feedback(store, action)
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        s = store._state(c)
        pet = s.setdefault('pet', {'bond': 0, 'interactions': 0, 'stage': 0, 'last_action': None})
        pet['bond'] = min(100, pet['bond'] + 1)
        pet['interactions'] += 1
        if action == 'pet':pet['touch_count']=pet.get('touch_count',0)+1
        pet['last_action'] = {'kind': action, 'time': time.time()}
        if action == 'feed':
            pet['feed_count'] = pet.get('feed_count', 0) + 1
            s['world']['energy'] = min(40, s['world']['energy']+5)
        store._save(c, s)
        store._event(c, 'interaction', {'action': action, 'simulated': True})
    snack = 'guilmon_bread' if action == 'feed' and pet['feed_count'] % 16 == 0 else 'round_bread'
    return {'action': action, 'reply': '发现隐藏彩蛋：基尔兽面包！' if action == 'feed' and snack == 'guilmon_bread' else replies[action],
            'snack': snack if action == 'feed' else None, 'bond': pet['bond'], 'simulated': True}

