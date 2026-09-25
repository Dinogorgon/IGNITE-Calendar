"""Run the calendar on your computer, with a working "Update now" button.

    python serve.py        (or double-click start.bat)
"""
import functools
import io
import json
import sys
import threading
import traceback
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import update

PORT = 8321
DOCS = Path(__file__).parent / "docs"
lock = threading.Lock()


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/status":
            return self._json({"mode": "local"})
        super().do_GET()

    def do_POST(self):
        if self.path != "/api/update":
            return self.send_error(404)
        out = io.StringIO()
        with lock:  # one update at a time
            try:
                update.run(log=lambda m: (print(m), out.write(m + "\n")))
            except Exception:
                out.write(traceback.format_exc())
        self._json({"log": out.getvalue()})

    def _json(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if not (DOCS / "events.json").exists():
        print("First run: collecting events…")
        update.run()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(Handler, directory=str(DOCS)))
    url = f"http://localhost:{PORT}"
    print(f"IGNITE calendar running at {url}  (close this window to stop)")
    if "--no-browser" not in sys.argv:
        webbrowser.open(url)
    server.serve_forever()
