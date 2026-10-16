#!/usr/bin/env bash
set -euo pipefail
ROOT=/root/autodl-tmp/DigitalMonster
for gpu in 0 1; do
  seed=11
  if [ "$gpu" = 1 ]; then seed=23; fi
  run="maze-seed-$seed"
  if tmux has-session -t "dm-$run" 2>/dev/null; then echo "$run already running"; continue; fi
  if [ -f "$ROOT/data/research/$run/report.json" ]; then echo "$run already completed"; continue; fi
  install -d -o digitalmonster -g digitalmonster -m 700 "$ROOT/data/research/$run"
  tmux new-session -d -s "dm-$run" "cd $ROOT/app && exec setpriv --reuid=digitalmonster --regid=digitalmonster --init-groups --no-new-privs $ROOT/runtime/bin/python -m digitalmon.maze_train --device cuda:$gpu --seed $seed --maps 8192 --steps 12000 --batch 256 --seconds 1800 --output $ROOT/data/research/$run >> $ROOT/data/research/$run/train.log 2>&1"
  echo "started $run on GPU $gpu, 1800-second wall-clock budget"
done

