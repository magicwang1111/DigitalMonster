"""Task cleanup adapted from MineDojo/Voyager CurriculumAgent.clean_up_tasks.
Copyright (c) 2023 MineDojo Team. MIT; see vendor/VOYAGER-LICENSE.
Persistence is supplied by the organism's existing SQLite transaction.
"""
def clean_up_tasks(completed_tasks, failed_tasks):
    updated_completed_tasks = []
    updated_failed_tasks = list(failed_tasks)
    for task in completed_tasks:
        if task not in updated_completed_tasks:
            updated_completed_tasks.append(task)
    for task in updated_completed_tasks:
        while task in updated_failed_tasks:
            updated_failed_tasks.remove(task)
    return updated_completed_tasks, updated_failed_tasks

PAGES=('random','sqlite3','math','collections','datetime','json','statistics','pathlib',
       'itertools','functools','heapq','bisect')

def next_task(brain):
    completed=set(brain.get('completed_tasks',[]))
    failed=brain.get('failed_tasks',[])
    urls=['https://docs.python.org/3/library/'+p+'.html' for p in PAGES]
    return min((u for u in urls if u not in completed),
               key=lambda u:failed.count(u),default=None)
