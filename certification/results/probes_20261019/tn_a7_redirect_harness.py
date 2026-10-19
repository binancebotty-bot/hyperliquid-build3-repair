import json, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
sys.path.insert(0, '.')
import exchange_truth as X

hits = {'a': 0, 'b': 0}
B_PORT = 18081
A_PORT = 18080

class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass
    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        self.rfile.read(n)
        hits['a' if self.server.server_port == A_PORT else 'b'] += 1
        if self.server.server_port == A_PORT:
            self.send_response(307)
            self.send_header('Location', f'http://127.0.0.1:{B_PORT}/info')
            self.send_header('Content-Length', '0')
            self.end_headers()
        else:
            body = b'{"ok":true}'
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

for p in (A_PORT, B_PORT):
    s = HTTPServer(('127.0.0.1', p), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()

try:
    r = X.http_post(f'http://127.0.0.1:{A_PORT}/info', {'type': 'meta'}, 3)
    out = {'TN-A7': {'origin_hits': hits['a'], 'foreign_origin_hits': hits['b'],
                     'status': getattr(r, 'status_code', None),
                     'verdict': 'REDIRECT_FOLLOWED_TO_FOREIGN_ORIGIN' if hits['b'] else 'REDIRECT_REFUSED'}}
except Exception as e:
    out = {'TN-A7': {'origin_hits': hits['a'], 'foreign_origin_hits': hits['b'], 'error': repr(e)[:200],
                     'verdict': 'REDIRECT_FOLLOWED_TO_FOREIGN_ORIGIN' if hits['b'] else 'REDIRECT_REFUSED_OR_ERROR'}}
print(json.dumps(out))
