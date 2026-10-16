import argparse
import json
import secrets
import signal
import threading
from pathlib import Path

from .runtime import Runtime
from .server import make_server
from .store import Store


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--data', default='data')
    p.add_argument('--port', type=int, default=8765)
    p.add_argument('--gpu', action='store_true')
    p.add_argument('--config', default='config/resources.json')
    args = p.parse_args()
    data = Path(args.data).resolve()
    data.mkdir(parents=True, exist_ok=True)
    # One service per database, including across different HTTP ports.
    lock = (data/'service.lock').open('a+b')
    try:
        if __import__('os').name == 'nt':
            import msvcrt
            lock.seek(0)
            lock.write(b'0')
            lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        raise SystemExit('another organism service owns this database')
    token_path = data/'access.token'
    if not token_path.exists():
        token_path.write_text(secrets.token_urlsafe(32), encoding='utf-8')
        token_path.chmod(0o600)
    token = token_path.read_text(encoding='utf-8').strip()
    store = Store(data/'life.sqlite')
    store.recover()
    config = json.loads(Path(args.config).read_text(encoding='utf-8'))
    runtime = Runtime(store, data, args.gpu, config)
    server = make_server(runtime, token, args.port)
    workers = [threading.Thread(target=f, daemon=True) for f in (runtime.activity_loop, runtime.work_loop)]
    for worker in workers:
        worker.start()

    def stop(*_):
        runtime.shutdown.set()
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print(f'DigitalMonster listening at http://127.0.0.1:{args.port}; token stored in {token_path}', flush=True)
    try:
        server.serve_forever()
    finally:
        runtime.shutdown.set()
        for worker in workers:
            worker.join(timeout=25)
        server.server_close()
        lock.close()


if __name__ == '__main__':
    main()
