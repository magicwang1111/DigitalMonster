"""Finite GPU distillation of a learned Q policy; exports a CPU-readable policy."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

from .learning import train, evaluate, validate


def run(output, seed=7, iterations=1200, device='cuda:0', cancelled=lambda: False):
    import torch
    torch.set_num_threads(2)
    torch.manual_seed(seed)
    if not torch.cuda.is_available() and device.startswith('cuda'):
        raise RuntimeError('CUDA unavailable: will not report CPU training as GPU training')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    teacher, training = train(seed, 6000, cancelled=cancelled)
    keys = sorted(teacher)
    x = torch.tensor([[int(v) for v in k.split(',')] for k in keys], device=device)
    x = torch.nn.functional.one_hot(x, 5).float().flatten(1)
    y = torch.tensor([max(range(4), key=lambda a: teacher[k][a]) for k in keys], device=device)
    model = torch.nn.Sequential(torch.nn.Linear(20, 128), torch.nn.ReLU(),
        torch.nn.Linear(128, 128), torch.nn.ReLU(), torch.nn.Linear(128, 4)).to(device)
    before = next(model.parameters()).detach().clone()
    optim = torch.optim.Adam(model.parameters(), lr=0.003)
    start = time.monotonic()
    loss_initial = None
    for i in range(iterations):
        if i % 20 == 0 and (cancelled() or time.monotonic() - start > 120):
            raise InterruptedError('GPU training cancelled or time budget exceeded')
        logits = model(x)
        loss = torch.nn.functional.cross_entropy(logits, y)
        if loss_initial is None:
            loss_initial = loss.item()
        optim.zero_grad()
        loss.backward()
        optim.step()
    with torch.no_grad():
        values = model(x).cpu().tolist()
        changed = bool(torch.any(next(model.parameters()) != before).item())
    policy = dict(zip(keys, values))
    validate(policy)
    checkpoint = output / 'model.pt'
    torch.save(model.state_dict(), checkpoint)
    metrics = {'algorithm': 'GPU MLP distillation of experience-trained Q policy',
               'device': device, 'gpu': torch.cuda.get_device_name(device) if device.startswith('cuda') else 'CPU',
               'torch': torch.__version__, 'seed': seed, 'iterations': iterations,
               'states': len(keys), 'parameters_changed': changed, 'loss_initial': loss_initial,
               'loss_final': loss.item(), 'seconds': time.monotonic()-start,
               'teacher': training, 'candidate': evaluate(policy), 'random': evaluate({}),
               'checkpoint_sha256': hashlib.sha256(checkpoint.read_bytes()).hexdigest()}
    for name, value in [('policy.json', policy), ('metrics.json', metrics)]:
        tmp = output / (name + '.tmp')
        tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(tmp, output / name)
    return metrics


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--seed', type=int, default=7)
    parser.add_argument('--device', default='cuda:0')
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.seed, device=args.device), ensure_ascii=False))
