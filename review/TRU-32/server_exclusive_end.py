# Serves ksea_window's 76 recorded observations, filtered like the service: start/end
# inclusive, newest first, `limit` keeps the newest. Logs every request's query.
import json, sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
rec = json.load(open(sys.argv[1]))["payload"]
feats = rec["features"]
ts = lambda f: datetime.fromisoformat(f["properties"]["timestamp"].replace("Z", "+00:00"))
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
        print("GET", q, flush=True)
        limit = int(q.get("limit", 500))
        if not 1 <= limit <= 500:
            body = json.dumps({"status": 400, "title": "Bad limit"}).encode()
            self.send_response(400); self.send_header("content-type", "application/problem+json"); self.end_headers(); self.wfile.write(body); return
        rows = [f for f in feats
                if ("start" not in q or ts(f) >= datetime.fromisoformat(q["start"].replace("Z", "+00:00")))
                and ("end" not in q or ts(f) < datetime.fromisoformat(q["end"].replace("Z", "+00:00")))]
        rows.sort(key=ts, reverse=True)
        body = json.dumps({**{k: v for k, v in rec.items() if k != "features"}, "features": rows[:limit]}).encode()
        self.send_response(200); self.send_header("content-type", "application/geo+json"); self.end_headers(); self.wfile.write(body)
HTTPServer(("127.0.0.1", int(sys.argv[2])), H).serve_forever()
