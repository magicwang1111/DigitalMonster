import hmac
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs


def make_server(runtime, token, port=8765):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, code, value, content_type='application/json; charset=utf-8'):
            raw = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def authorized(self):
            host = self.headers.get('Host', '')
            if host not in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'):
                return False
            origin = self.headers.get('Origin')
            if origin and origin not in (f'http://{host}',):
                return False
            return hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer '+token)

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == '/':
                return self.send(200, (Path(__file__).parent/'static'/'index.html').read_bytes(), 'text/html; charset=utf-8')
            if path == '/health':
                return self.send(200, {'status': 'ok'})
            if path == '/pet/evolution-pixel.png':
                return self.send(200, (Path(__file__).parent/'static'/'pet'/'evolution-pixel.png').read_bytes(), 'image/png')
            if not self.authorized():
                return self.send(403, {'error': 'authorization required'})
            if path == '/api/state':
                state = runtime.store.snapshot()
                state['capabilities'] = {'language_model': False, 'internet': True, 'gpu_training': runtime.gpu,
                                         'autonomy': 'rule-selected goals and learned navigation policy'}
                state['resources'] = runtime.config.get('resources', [])
                return self.send(200, state)
            if path == '/api/memories':
                query = parse_qs(urlsplit(self.path).query).get('q', [''])[0][:500]
                return self.send(200, runtime.store.memories(query))
            if path == '/api/pet':
                from .pet import status
                return self.send(200, status(runtime.store, runtime.data))
            if path == '/api/experiments':
                reports = []
                for p in sorted((runtime.data / 'research').glob('*/progress.json'))[-12:]:
                    try:
                        reports.append({'run': p.parent.name, **json.loads(p.read_text(encoding='utf-8'))})
                    except (OSError, ValueError):
                        pass
                return self.send(200, reports)
            return self.send(404, {'error': 'not found'})

        def do_POST(self):
            if not self.authorized():
                return self.send(403, {'error': 'authorization or same-origin check failed'})
            try:
                if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                    raise ValueError('JSON required')
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 65536:
                    raise ValueError('invalid request size')
                self.connection.settimeout(5)
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError('JSON object required')
                if self.path == '/api/control':
                    runtime.control(body.get('action'))
                    result = {'ok': True}
                elif self.path == '/api/message':
                    mid = runtime.store.remember(body.get('text'))
                    result = {'memory_id': mid, 'reply': '已保存这条记忆。当前未接入语言生成模型；这是一条系统回执。'}
                elif self.path == '/api/interact':
                    from .pet import interact
                    result = interact(runtime.store, body.get('action'))
                elif self.path == '/api/research':
                    result = {'job_id': runtime.queue('research', {'url': body.get('url')})}
                elif self.path == '/api/explore':
                    sources=runtime.store.snapshot().get('brain',{}).get('explored_sources',[])
                    pages=['random','sqlite3','math','collections','datetime','json','statistics','pathlib','itertools','functools','heapq','bisect']
                    url='https://docs.python.org/3/library/'+pages[len(sources)%len(pages)]+'.html'
                    result={'job_id':runtime.queue('research',{'url':url}), 'reply':'已开始联网探索，完成后记入同一个体的来源记录。'}
                elif self.path == '/api/train':
                    result = {'job_id': runtime.queue('train', body)}
                elif self.path == '/api/rollback':
                    version = body.get('version')
                    if type(version) is not int:
                        raise ValueError('version must be an integer')
                    runtime.store.rollback(version)
                    result = {'ok': True}
                else:
                    return self.send(404, {'error': 'not found'})
                return self.send(200, result)
            except (ValueError, TypeError, KeyError, OSError) as exc:
                return self.send(400, {'error': str(exc)[:300]})
            except Exception:
                return self.send(500, {'error': 'operation failed; inspect service logs'})

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    return server

