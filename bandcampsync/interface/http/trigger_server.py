"""A tiny HTTP server exposing the sync service to a browser or a phone.

Deliberately stdlib-only (http.server) rather than a Flask/FastAPI dependency:
the surface here is three routes on a personal, tailnet-only endpoint, not a
public API - a framework would be pure overhead.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from bandcampsync.domain import LogTail, SyncState

PAGE_HTML = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BandcampSync</title>
<style>
  body { font-family: -apple-system, system-ui, sans-serif; max-width: 640px;
         margin: 2rem auto; padding: 0 1rem; background: #111; color: #eee; }
  h1 { font-size: 1.3rem; }
  button { font-size: 1.1rem; padding: 0.9rem 1.5rem; width: 100%;
           border: none; border-radius: 8px; background: #1d9bf0; color: white; }
  button:disabled { background: #444; }
  #status { margin: 1rem 0; padding: 0.75rem; border-radius: 8px; background: #1c1c1c; }
  #log { background: #000; color: #9ada6c; font-family: monospace; font-size: 0.75rem;
         padding: 0.75rem; height: 40vh; overflow-y: auto; border-radius: 8px;
         white-space: pre-wrap; }
</style>
</head>
<body>
<h1>BandcampSync</h1>
<button id="syncBtn" onclick="triggerSync()">Sync now</button>
<div id="status">loading...</div>
<div id="log"></div>
<script>
async function triggerSync() {
  const btn = document.getElementById('syncBtn');
  btn.disabled = true;
  try {
    const resp = await fetch('/sync', { method: 'POST' });
    const body = await resp.json();
    document.getElementById('status').textContent = body.message || 'requested';
  } finally {
    setTimeout(() => { btn.disabled = false; }, 2000);
  }
}
async function poll() {
  try {
    const resp = await fetch('/status');
    const s = await resp.json();
    document.getElementById('status').textContent =
      `status: ${s.status} | last finished: ${s.last_run_finished || 'never'} | ` +
      `last result: ${s.last_result || 'n/a'} | next scheduled: ${s.next_scheduled || 'n/a'}`;
    const logEl = document.getElementById('log');
    const wasAtBottom = logEl.scrollTop + logEl.clientHeight >= logEl.scrollHeight - 10;
    logEl.textContent = s.log_tail.join('\\n');
    if (wasAtBottom) logEl.scrollTop = logEl.scrollHeight;
  } catch (e) {
    document.getElementById('status').textContent = 'error contacting service';
  }
}
poll();
setInterval(poll, 3000);
</script>
</body>
</html>
"""


def make_handler(
    state: SyncState, log_tail: LogTail, wake_event: threading.Event
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            pass  # don't spam the container's own stdout with HTTP access logs

        def address_string(self) -> str:
            # BaseHTTPRequestHandler.log_request() calls this (reverse DNS via
            # socket.getfqdn()) before log_message() ever gets a chance to no-op
            # it, adding multi-second latency to every request. Skip it - we
            # don't log requests at all, so the hostname is never used.
            return self.client_address[0]

        def _send_json(self, payload: dict[str, Any], code: int = 200) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path == "/":
                body = PAGE_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/status":
                payload: dict[str, Any] = dict(state.to_dict())
                payload["log_tail"] = log_tail.tail()
                self._send_json(payload)
            else:
                self._send_json({"error": "not found"}, code=404)

        def do_POST(self) -> None:
            if self.path == "/sync":
                if state.to_dict()["status"] == "running":
                    self._send_json({"message": "sync already in progress"})
                else:
                    wake_event.set()
                    self._send_json({"message": "sync requested"}, code=202)
            else:
                self._send_json({"error": "not found"}, code=404)

    return Handler


def start_http_server(
    port: int,
    state: SyncState,
    log_tail: LogTail,
    wake_event: threading.Event,
    host: str = "0.0.0.0",  # noqa: S104 - needs to be reachable from the tailscale sidecar
) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), make_handler(state, log_tail, wake_event))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
