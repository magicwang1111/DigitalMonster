#!/usr/bin/env bash
set -euo pipefail
ROOT=/root/autodl-tmp/DigitalMonster
case "${1:-status}" in
  start)
    if tmux has-session -t digitalmonster 2>/dev/null; then echo 'service already running'; exit 0; fi
    tmux new-session -d -s digitalmonster "cd $ROOT/app && exec setpriv --reuid=digitalmonster --regid=digitalmonster --init-groups --no-new-privs $ROOT/runtime/bin/python -m digitalmon --data $ROOT/data --gpu >> $ROOT/data/service.log 2>&1"
    ;;
  stop)
    # Only this project's process, identified by its exact module and data directory.
    pgrep -u digitalmonster -f "python -m digitalmon --data $ROOT/data" | xargs -r kill -TERM
    ;;
  status)
    tmux has-session -t digitalmonster 2>/dev/null && echo 'tmux: running' || true
    curl --fail --silent http://127.0.0.1:8765/health
    ;;
  *) echo 'usage: remote-service.sh start|stop|status'; exit 2;;
esac

