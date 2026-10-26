#!/usr/bin/env python3
"""Serve the STOOPIDS app and keep it fresh.
   python3 serve.py [--port 8765] [--interval 10]
Refreshes data on start and every N minutes (every 3 min in the evenings ET during the season is not needed: ESPN is cheap, 10 is fine).
Open http://localhost:8765/ . Also: GET /refresh forces a refresh now."""
import argparse, json, http.server, socketserver, threading, subprocess, sys, os, time
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
lock = threading.Lock()
def refresh():
    if lock.acquire(blocking=False):
        try:
            r = subprocess.run([sys.executable, "refresh.py"], capture_output=True, text=True, timeout=600)
            print(time.strftime("%H:%M:%S"), "refresh rc=%s" % r.returncode, (r.stderr.strip().splitlines() or [""])[-1], flush=True)
        finally:
            lock.release()
def loop(mins):
    while True:
        refresh(); time.sleep(mins * 60)
import bets as B
EDIT_TOKEN = None
class H(http.server.SimpleHTTPRequestHandler):
    def _can_edit(self):
        if EDIT_TOKEN:
            return self.headers.get("X-Edit-Token") == EDIT_TOKEN
        return self.client_address[0] in ("127.0.0.1", "::1")
    def _json(self, code, obj):
        b = json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        if not self.path.startswith("/api/bets"):
            return self._json(404, {"ok": False})
        if not self._can_edit():
            return self._json(403, {"ok": False, "error": "editing is only allowed from the machine running serve.py (or with --edit-token)"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            if self.path == "/api/bets/add":
                n = B.add_bet(body["bet"])
            elif self.path == "/api/bets/update":
                B.update_bet(body["n"], body["patch"]); n = body["n"]
            else:
                return self._json(404, {"ok": False})
        except Exception as ex:
            return self._json(400, {"ok": False, "error": str(ex)})
        refresh()
        self._json(200, {"ok": True, "n": n})
    def do_GET(self):
        if self.path.startswith("/api/ping"):
            return self._json(200, {"edit": self._can_edit()})
        if self.path.startswith("/refresh"):
            threading.Thread(target=refresh, daemon=True).start()
            self.send_response(200); self.end_headers(); self.wfile.write(b"refresh started\n"); return
        return super().do_GET()
    def end_headers(self):
        self.send_header("Cache-Control", "no-store"); super().end_headers()
    def log_message(self, *a): pass
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, default=8765); ap.add_argument("--interval", type=int, default=10)
    ap.add_argument("--edit-token", help="allow remote ledger edits from clients sending header X-Edit-Token")
    a = ap.parse_args()
    EDIT_TOKEN = a.edit_token
    threading.Thread(target=loop, args=(a.interval,), daemon=True).start()
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("0.0.0.0", a.port), H) as s:
        print("STOOPIDS on http://0.0.0.0:%d" % a.port, flush=True); s.serve_forever()
