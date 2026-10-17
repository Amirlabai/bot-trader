"""Localhost Evolve lab (scratch-only). Not part of GitHub Pages.

Usage:
  python scratch\\evolve_lab\\server.py
  open http://127.0.0.1:8767
"""
from __future__ import annotations

import json
import os
import threading
import traceback
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import engine

HERE = os.path.dirname(os.path.abspath(__file__))
HOST, PORT = '127.0.0.1', 8767
MARKETS = ('crypto', 'commodities', 'forex', 'stocks')
JOBS: dict[str, dict] = {}
LOCK = threading.Lock()


def _run_job(job: dict) -> None:
    def progress(stage, i, n, note):
        job.update(stage=stage, i=i, n=n, note=note)

    try:
        job['report'] = engine.run_cycle(job['market'], progress=progress)
        job['status'] = 'done'
    except Exception as e:  # surfaced in the UI
        traceback.print_exc()
        job.update(status='error', error=str(e))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=HERE, **kw)

    def log_message(self, *a):
        pass

    def _json(self, obj, status=200):
        body = json.dumps(obj).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _market(self, q) -> str:
        m = (q.get('market') or ['crypto'])[0]
        if m not in MARKETS:
            raise ValueError(f'Unknown market {m}')
        return m

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path == '/api/state':
                m = self._market(q)
                return self._json({'state': engine.state(m), 'feedback': engine.feedback(m)})
            if u.path.startswith('/api/job/'):
                job = JOBS.get(u.path.rsplit('/', 1)[1])
                if not job:
                    return self._json({'error': 'Unknown job'}, 404)
                return self._json({k: v for k, v in job.items()})
        except Exception as e:
            return self._json({'error': str(e)}, 400)
        return super().do_GET()

    def do_POST(self):
        u = urlparse(self.path)
        n = int(self.headers.get('Content-Length') or 0)
        body = json.loads(self.rfile.read(n) or b'{}')
        try:
            if u.path == '/api/run':
                m = self._market({'market': [body.get('market', 'crypto')]})
                with LOCK:
                    if any(j['status'] == 'running' for j in JOBS.values()):
                        return self._json({'error': 'A retune is already running.'}, 409)
                    jid = uuid.uuid4().hex[:8]
                    JOBS[jid] = job = {'id': jid, 'market': m, 'status': 'running', 'stage': 'Starting', 'i': 0, 'n': 1,
                                       'note': ''}
                threading.Thread(target=_run_job, args=(job,), daemon=True).start()
                return self._json({'id': jid})
            if u.path == '/api/promote':
                job = JOBS.get(body.get('id'))
                if not job or job['status'] != 'done':
                    return self._json({'error': 'No finished run to promote.'}, 400)
                engine.promote(job['report'], force=bool(body.get('force')))
                job['status'] = 'promoted'
                return self._json({'ok': True})
            if u.path == '/api/reject':
                job = JOBS.get(body.get('id'))
                if not job or job['status'] != 'done':
                    return self._json({'error': 'No finished run to reject.'}, 400)
                engine.reject(job['report'])
                job['status'] = 'rejected'
                return self._json({'ok': True})
            if u.path == '/api/rollback':
                engine.rollback(self._market({'market': [body.get('market', 'crypto')]}))
                return self._json({'ok': True})
        except Exception as e:
            return self._json({'error': str(e)}, 400)
        self._json({'error': 'Not found'}, 404)


if __name__ == '__main__':
    print(f'Evolve lab: http://{HOST}:{PORT}')
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
