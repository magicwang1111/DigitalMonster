"""Finite GPU training on self-generated mazes. No language model involved.

Supervision is derived from the simulator's BFS oracle, not internet text.
Validation chooses checkpoints; a separate final test set is evaluated once.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import time

from .maze import generate, rollout, MOVES


def save_json(path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(tmp, path)


def make_model(torch, width=48, rounds=12):
    class Planner(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.embed = torch.nn.Conv2d(2, width, 3, padding=1)
            self.propagate = torch.nn.Conv2d(width+2, width, 3, padding=1)
            self.head = torch.nn.Conv2d(width, 4, 1)

        def forward(self, x):
            h = torch.relu(self.embed(x))
            for _ in range(rounds):
                h = torch.relu(self.propagate(torch.cat([h, x], dim=1)))
            return self.head(h)
    return Planner()


def tensors(torch, mazes, device):
    import numpy as np
    walls = np.asarray([m['walls'] for m in mazes], dtype=np.float32)
    goals = np.zeros_like(walls)
    for i, m in enumerate(mazes):
        goals[i, m['goal'][1], m['goal'][0]] = 1
    x = torch.from_numpy(np.stack([walls, goals], axis=1)).to(device)
    masks = torch.tensor([m['optimal'] for m in mazes], dtype=torch.bool, device=device).permute(0, 3, 1, 2)
    return x, masks


def evaluate_model(torch, model, mazes, device):
    results = []
    correct, count = 0, 0
    model.eval()
    with torch.no_grad():
        for offset in range(0, len(mazes), 128):
            batch = mazes[offset:offset+128]
            x, masks = tensors(torch, batch, device)
            actions = model(x).argmax(1)
            valid = masks.any(1)
            correct += (masks.gather(1, actions.unsqueeze(1)).squeeze(1) & valid).sum().item()
            count += valid.sum().item()
            results.extend(rollout(m, a) for m, a in zip(batch, actions.cpu().tolist()))
    model.train()
    successes = [r for r in results if r['success']]
    return {'success_rate': len(successes)/len(results), 'episodes': len(results),
            'optimal_action_accuracy': correct/max(count, 1),
            'mean_steps_with_failure_penalty': sum(r['steps'] for r in results)/len(results),
            'path_efficiency_on_success': sum(r['shortest']/max(r['steps'],1) for r in successes)/max(len(successes),1),
            'outcomes': results}


def baseline(mazes, kind):
    results = []
    for m in mazes:
        rng = random.Random(m['seed']+900000)
        actions = []
        for y, row in enumerate(m['walls']):
            cells = []
            for x in range(len(row)):
                if kind == 'random':
                    a = rng.randrange(4)
                else:
                    candidates = []
                    for a, (dx, dy) in enumerate(MOVES):
                        nx, ny = x+dx, y+dy
                        if 0 <= nx < len(row) and 0 <= ny < len(row) and not m['walls'][ny][nx]:
                            candidates.append((abs(nx-m['goal'][0])+abs(ny-m['goal'][1]), a))
                    a = min(candidates)[1] if candidates else 0
                cells.append(a)
            actions.append(cells)
        results.append(rollout(m, actions))
    return {'success_rate': sum(r['success'] for r in results)/len(results),
            'mean_steps_with_failure_penalty': sum(r['steps'] for r in results)/len(results),
            'episodes': len(results), 'kind': kind+' stationary policy'}


def run(args):
    import torch
    torch.set_num_threads(4)
    torch.manual_seed(args.seed)
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA required for this experiment')
    torch.backends.cudnn.benchmark = True
    torch.set_float32_matmul_precision('high')
    device = args.device
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    config = vars(args).copy()
    config.update({'algorithm': 'recurrent convolutional planner, simulator-supervised learning',
                   'torch': torch.__version__, 'gpu': torch.cuda.get_device_name(device),
                   'training_seeds': [args.seed*100000, args.seed*100000+args.maps-1],
                   'validation_seeds': [20000000, 20000127], 'test_seeds': [30000000,30000511],
                   'claim': 'navigation learning on procedural 9x9 maps; not general intelligence'})
    save_json(out/'config.json', config)
    save_json(out/'progress.json', {'status': 'generating-data', 'step': 0})
    mazes = [generate(args.seed*100000+i) for i in range(args.maps)]
    x, masks = tensors(torch, mazes, device)
    del mazes
    validation = [generate(20000000+i) for i in range(128)]
    model = make_model(torch).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.0001)
    initial_weights = next(model.parameters()).detach().clone()
    best = -1
    progress = {}
    history = []
    loss_initial = None
    # 60 seconds reserved for final evaluation and artifacts.
    for step in range(1, args.steps+1):
        if (out/'STOP').exists() or time.monotonic()-start > args.seconds-60:
            break
        idx = torch.randint(0, len(x), (args.batch,), device=device)
        batch_masks = masks[idx]
        valid = batch_masks.any(1)
        logits = model(x[idx])
        # Multi-label optimum: all equally short actions are acceptable.
        logp = torch.log_softmax(logits, dim=1)
        loss = -torch.logsumexp(logp.masked_fill(~batch_masks, -1e4), dim=1)[valid].mean()
        if not torch.isfinite(loss):
            raise RuntimeError('non-finite training loss')
        if loss_initial is None:
            loss_initial = loss.item()
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        if step == 1 or step % 100 == 0:
            progress = {'status': 'training', 'step': step, 'loss': loss.item(),
                        'elapsed_seconds': time.monotonic()-start, 'seed': args.seed,
                        'gpu': config['gpu'], 'samples_seen': step*args.batch,
                        'gpu_peak_memory_mib': torch.cuda.max_memory_allocated(device)/1024**2}
            if step == 1 or step % 500 == 0:
                metric = evaluate_model(torch, model, validation, device)
                progress['success_rate'] = metric['success_rate']
                progress['validation'] = {k:v for k,v in metric.items() if k != 'outcomes'}
                if metric['success_rate'] > best:
                    best = metric['success_rate']
                    torch.save(model.state_dict(), out/'best.pt.tmp')
                    os.replace(out/'best.pt.tmp', out/'best.pt')
                    progress['best_step'] = step
            elif history:
                progress['success_rate'] = history[-1].get('success_rate', best)
            history.append(progress.copy())
            save_json(out/'progress.json', progress)
            save_json(out/'history.json', history)
            print(json.dumps(progress), flush=True)
    if not (out/'best.pt').exists():
        raise RuntimeError('no checkpoint produced before training stopped')
    changed = bool(torch.any(initial_weights != next(model.parameters())).item())
    model.load_state_dict(torch.load(out/'best.pt', map_location=device, weights_only=True))
    test_mazes = [generate(30000000+i) for i in range(512)]
    result = evaluate_model(torch, model, test_mazes, device)
    report = {**config, 'status': 'completed', 'step': step-1 if step <= args.steps and (out/'STOP').exists() else step,
              'elapsed_seconds': time.monotonic()-start, 'loss_initial': loss_initial,
              'parameters_changed': changed, 'best_validation_success': best,
              'test': result, 'success_rate': result['success_rate'],
              'random_baseline': baseline(test_mazes, 'random'),
              'greedy_baseline': baseline(test_mazes, 'greedy'),
              'checkpoint_sha256': hashlib.sha256((out/'best.pt').read_bytes()).hexdigest()}
    # Export the trained network's fixed-world behavior for adoption by the live organism.
    from .world import CELLS, WALLS
    exported = {}
    with torch.no_grad():
        for gx, gy in CELLS:
            walls = [[int((cx,cy) in WALLS) for cx in range(5)] for cy in range(5)]
            inp = torch.zeros((1,2,5,5), device=device)
            inp[0,0] = torch.tensor(walls, device=device)
            inp[0,1,gy,gx] = 1
            logits = model(inp)[0].cpu()
            for px, py in CELLS:
                if (px,py) != (gx,gy):
                    exported[f'{px},{py},{gx},{gy}'] = logits[:,py,px].tolist()
    save_json(out/'policy.json', exported)
    save_json(out/'report.json', report)
    save_json(out/'progress.json', {k:v for k,v in report.items() if k not in ('test',)})
    print(json.dumps({k:v for k,v in report.items() if k != 'test'}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--device', default='cuda:0')
    parser.add_argument('--seed', type=int, default=11)
    parser.add_argument('--maps', type=int, default=8192)
    parser.add_argument('--steps', type=int, default=12000)
    parser.add_argument('--batch', type=int, default=256)
    parser.add_argument('--seconds', type=int, default=1800)
    args = parser.parse_args()
    if not (1 <= args.maps <= 32768 and 1 <= args.steps <= 100000 and
            1 <= args.batch <= 1024 and 90 <= args.seconds <= 7200 and 1 <= args.seed <= 100):
        parser.error('experiment exceeds allowed limits')
    run(args)
