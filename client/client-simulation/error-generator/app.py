import http.server
import json
import os
import sys
import threading
import time


PORT = int(os.environ.get("PORT", "8080"))
ERROR_INTERVAL_SECONDS = int(os.environ.get("ERROR_INTERVAL_SECONDS", "30"))


def log_error(reason: str) -> None:
    payload = {
        "severity": "ERROR",
        "service": "checkout",
        "component": "aegis-error-generator",
        "reason": reason,
        "message": "simulated checkout failure",
    }
    print(json.dumps(payload), file=sys.stderr, flush=True)


def emit_periodic_errors() -> None:
    while True:
        log_error("periodic")
        time.sleep(ERROR_INTERVAL_SECONDS)


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok\n")
            return

        if self.path == "/fail":
            log_error("manual-http-trigger")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"simulated failure\n")
            return

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"aegis error generator\n")

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    threading.Thread(target=emit_periodic_errors, daemon=True).start()
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()
