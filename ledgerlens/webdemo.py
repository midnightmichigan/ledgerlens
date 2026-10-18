#!/usr/bin/env python3
"""LedgerLens web demo (stdlib-only http.server).

Run:  python3 -m ledgerlens.webdemo
Then: http://127.0.0.1:8137/

Paste CSV or loose-text receipts (or load the labeled-synthetic fixture),
get back: categorized books, category totals, overdue-invoice radar,
3-month cash-flow forecast, and action items. All data stays on this
machine; the only pre-loaded data is labeled SYNTHETIC.
"""
import datetime
import html
import json
import sys
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ledgerlens.parse import parse_csv, parse_loose
from ledgerlens.categorize import categorize_all
from ledgerlens.report import build_report

PORT = 8137
HISTORY = []  # per-process run history (summary dicts only)

FIXTURE_CSV = """date,vendor,description,amount,kind,due,paid
2026-08-03,Acme Corp,Invoice #1041 web design retainer,1500.00,income,2026-09-02,yes
2026-08-05,Staples,office supplies paper and ink,42.99,expense,,
2026-08-12,Brightside LLC,Invoice #1042 copywriting project,850.00,income,2026-09-11,no
2026-08-15,Chipotle,client lunch meeting,18.40,expense,,
2026-08-22,DigitalOcean,GPU droplet hosting,24.00,expense,,
2026-09-02,Acme Corp,Invoice #1043 maintenance retainer,1500.00,income,2026-10-02,no
2026-09-06,Shell,gas mileage to client site,38.15,expense,,
2026-09-10,GitHub,copilot subscription,10.00,expense,,
2026-09-14,Verizon,phone bill business line,65.00,expense,,
2026-09-20,DotCo,Invoice #1044 logo design,600.00,income,2026-10-20,no
2026-10-01,Acme Corp,Invoice #1045 october retainer,1500.00,income,2026-11-01,no
2026-10-04,Staples,shipping labels packaging,21.75,expense,,
2026-10-06,Delta,flight to client onsite,289.00,expense,,
"""


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def money(v: float) -> str:
    return f"${v:,.2f}"


def conf_bar(conf: float) -> str:
    pct = int(round(max(0.0, min(1.0, conf)) * 100))
    color = "#2e7d32" if pct >= 70 else ("#f9a825" if pct >= 40 else "#c62828")
    return (
        f'<span style="display:inline-block;width:70px;background:#eee;'
        f'border-radius:3px;overflow:hidden;vertical-align:middle;">'
        f'<span style="display:inline-block;width:{pct}px;height:10px;'
        f'background:{color};"></span></span> {pct}%'
    )


CSS = """
body{font-family:system-ui,-apple-system,sans-serif;max-width:980px;margin:24px auto;
padding:0 16px;color:#1a1a1a;background:#fafafa;line-height:1.5}
.card{background:#fff;border:1px solid #e0e0e0;border-radius:10px;padding:18px;margin:14px 0;
box-shadow:0 1px 3px rgba(0,0,0,.06)}
h1{font-size:1.6em;margin:.2em 0}h2{font-size:1.2em;margin:.4em 0}
table{border-collapse:collapse;width:100%;font-size:.92em}
th,td{border:1px solid #e3e3e3;padding:6px 8px;text-align:left}
th{background:#f5f5f5}tr:nth-child(even) td{background:#fbfbfb}
textarea{width:100%;height:220px;font-family:ui-monospace,monospace;font-size:12px;
border:1px solid #ccc;border-radius:6px;padding:8px;box-sizing:border-box}
button,input[type=submit]{background:#1565c0;color:#fff;border:0;border-radius:6px;
padding:10px 18px;font-size:15px;cursor:pointer}
.badge{display:inline-block;font-size:.78em;padding:2px 10px;border-radius:12px;
background:#e8f5e9;color:#2e7d32;margin-left:8px}
.warn{background:#fff3e0;color:#e65100}.bad{background:#ffebee;color:#c62828}
.pill{display:inline-block;font-size:.8em;padding:1px 9px;border-radius:10px;
background:#e3f2fd;color:#1565c0;margin:2px 3px}
.footer{color:#777;font-size:.82em;margin-top:24px}
"""


def page(title: str, body: str) -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{esc(title)}</title><style>{CSS}</style></head><body>"
        f"<h1>LedgerLens <span class='badge'>local-first bookkeeping agent</span></h1>"
        f"{body}<div class='footer'>LedgerLens web demo — stdlib-only. "
        "Any pre-loaded data is labeled synthetic. Your pasted data never "
        "leaves this machine.</div></body></html>"
    )


def index_page() -> str:
    hist = "".join(
        f"<tr><td>{esc(h['ts'])}</td><td>{h['records']}</td>"
        f"<td>{money(h['income'])} / {money(h['expenses'])}</td>"
        f"<td>{h['overdue']}</td></tr>"
        for h in reversed(HISTORY[-8:])
    ) or "<tr><td colspan='4'>no analyses yet this session</td></tr>"
    body = (
        "<div class='card'><h2>1. Paste your books</h2>"
        "<p>CSV (<code>date,vendor,description,amount,kind,due,paid</code>) or "
        "plain-text receipt lines like <code>Staples office supplies $16.49</code>.</p>"
        "<form method='post' action='/analyze'>"
        f"<textarea name='data' placeholder='paste CSV or receipt lines here...'></textarea>"
        "<p><input type='submit' value='Analyze my books'> "
        "<button type='submit' formaction='/analyze?fixture=1' formmethod='get'>"
        "Load synthetic fixture instead</button></p></form></div>"
        "<div class='card'><h2>This session</h2>"
        "<table><tr><th>time</th><th>records</th><th>income / expenses</th>"
        f"<th>overdue</th></tr>{hist}</table></div>"
    )
    return page("LedgerLens — local-first bookkeeping", body)


def analyze_records(raw: str, as_of: datetime.date):
    """Parse mixed CSV/loose input; return (records, note)."""
    records = parse_csv(raw) + parse_loose(raw)
    note = None
    if not records:
        note = "Nothing parsed — paste CSV rows or lines like 'Staples office supplies $16.49'."
    return records, note


def report_page(records, as_of: datetime.date, source_label: str) -> str:
    rep = build_report(records, as_of)
    cat_rows = "".join(
        f"<tr><td>{esc(r.date)}</td><td>{esc(r.vendor)}</td>"
        f"<td>{money(r.amount)}</td><td>{esc(r.kind)}</td>"
        f"<td><span class='pill'>{esc(cat)}</span></td>"
        f"<td>{conf_bar(conf)}</td><td>{esc(', '.join(hits) or '—')}</td></tr>"
        for r, cat, conf, hits in categorize_all(records)
    )
    totals_rows = "".join(
        f"<tr><td>{esc(c)}</td><td style='text-align:right'>{money(t)}</td></tr>"
        for c, t in sorted(rep.category_totals.items(), key=lambda kv: -kv[1])
    )
    overdue_html = "".join(f"<li>{esc(x)}</li>" for x in rep.overdue) or "<li>none — books are clean</li>"
    actions_html = "".join(f"<li>{esc(x)}</li>" for x in rep.actions) or "<li>none</li>"
    forecast_html = "".join(f"<li>{esc(x)}</li>" for x in rep.forecast_lines) or "<li>not enough history</li>"
    HISTORY.append({
        "ts": datetime.datetime.now().strftime("%H:%M:%S"),
        "records": len(records),
        "income": rep.total_income,
        "expenses": rep.total_expenses,
        "overdue": len(rep.overdue),
    })
    body = (
        f"<div class='card'><h2>Bookkeeping report <span class='badge'>{esc(source_label)}</span></h2>"
        f"<p>{rep.categorized_count} records categorized, "
        f"{rep.uncategorized_count} uncategorized.</p>"
        f"<table><tr><th>Total income</th><th>Total expenses</th><th>Net</th></tr>"
        f"<tr><td>{money(rep.total_income)}</td><td>{money(rep.total_expenses)}</td>"
        f"<td><b>{money(rep.net)}</b></td></tr></table></div>"
        f"<div class='card'><h2>Category totals (tax-ready)</h2><table>"
        f"<tr><th>Category</th><th style='text-align:right'>Total</th></tr>{totals_rows}</table></div>"
        f"<div class='card'><h2>Overdue-invoice radar</h2><ul>{overdue_html}</ul></div>"
        f"<div class='card'><h2>3-month cash-flow forecast</h2><ul>{forecast_html}</ul></div>"
        f"<div class='card'><h2>Action items</h2><ul>{actions_html}</ul></div>"
        "<div class='card'><h2>Record-by-record categorization</h2><table>"
        "<tr><th>date</th><th>vendor</th><th>amount</th><th>kind</th>"
        f"<th>category</th><th>confidence</th><th>why</th></tr>{cat_rows}</table></div>"
        "<p><a href='/'>← analyze another set</a></p>"
    )
    return page("LedgerLens report", body)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _send(self, code: int, body: str, ctype: str = "text/html; charset=utf-8"):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/api/report"):
            if not HISTORY:
                self._send(200, json.dumps({"ok": False, "error": "no analyses this session"}),
                           "application/json")
                return
            last = HISTORY[-1]
            self._send(200, json.dumps({"ok": True, "last_analysis": last}), "application/json")
            return
        if self.path == "/" or self.path.startswith("/analyze"):
            if self.path.startswith("/analyze"):
                # fixture button: synthetic data, honestly labeled
                recs, _ = analyze_records(FIXTURE_CSV, datetime.date.today())
                self._send(200, report_page(recs, datetime.date.today(), "SYNTHETIC FIXTURE"))
                return
            self._send(200, index_page())
            return
        self._send(404, page("not found", "<div class='card'><h2>404</h2></div>"))

    def do_POST(self):
        if self.path != "/analyze":
            self._send(404, page("not found", "<div class='card'><h2>404</h2></div>"))
            return
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length > 200_000:
            self._send(413, page("too large", "<div class='card'><h2>Input too large (200 KB cap)</h2></div>"))
            return
        fields = parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
        raw = fields.get("data", [""])[0]
        recs, note = analyze_records(raw, datetime.date.today())
        if note:
            body = (f"<div class='card'><h2>No records parsed</h2><p>{esc(note)}</p>"
                    "<p><a href='/'>← back</a></p></div>")
            self._send(200, page("LedgerLens", body))
            return
        self._send(200, report_page(recs, datetime.date.today(), "your pasted data"))


def main() -> int:
    srv = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"LedgerLens web demo at http://127.0.0.1:{PORT}/  (Ctrl-C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
