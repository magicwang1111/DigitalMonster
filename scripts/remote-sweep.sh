#!/usr/bin/env bash
set -euo pipefail
ROOT=/root/autodl-tmp/DigitalMonster
# Two independent jobs per GPU, each allocator capped at 46% of physical memory.
# A fixed 30-minute wall-clock budget per experiment keeps the first report before 13:00 CST.
for spec in '0 31 96 24' '0 37 128 24' '1 43 96 32' '1 47 128 32'; do
  read -r gpu seed width rounds <<< "$spec"
  run="maze21-w$width-r$rounds-s$seed"
  if tmux has-session -t "dm-$run" 2>/dev/null || [ -f "$ROOT/data/research/$run/report.json" ]; then
    echo "$run already exists; not resubmitting"; continue
  fi
  install -d -o digitalmonster -g digitalmonster -m 700 "$ROOT/data/research/$run"
  tmux new-session -d -s "dm-$run" "cd $ROOT/app && exec setpriv --reuid=digitalmonster --regid=digitalmonster --init-groups --no-new-privs $ROOT/runtime/bin/python -m digitalmon.maze_train --device cuda:$gpu --seed $seed --maps 8192 --steps 30000 --batch 512 --seconds 1800 --size 21 --width $width --rounds $rounds --memory-fraction 0.46 --autobatch --output $ROOT/data/research/$run >> $ROOT/data/research/$run/train.log 2>&1"
  echo "started $run on GPU $gpu; auto batch / 46% memory cap / 1800 seconds"
done
