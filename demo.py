#!/usr/bin/env python3
"""LedgerLens end-to-end demo on SYNTHETIC fixture data.

Run:  python3 demo.py
"""
import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ledgerlens.parse import parse_csv, parse_loose
from ledgerlens.categorize import categorize_all
from ledgerlens.report import build_report, render_text

# NOTE: all names, vendors, and amounts below are SYNTHETIC fixtures.
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

FIXTURE_LOOSE = """
Staples office supplies $16.49
2026-10-08 Chipotle dinner with client $24.10
"""


def main() -> int:
    as_of = datetime.date(2026, 10, 12)
    records = parse_csv(FIXTURE_CSV) + parse_loose(FIXTURE_LOOSE)
    print(f"parsed {len(records)} records (synthetic fixtures)\n")

    print("-- categorization --")
    for r, cat, conf, hits in categorize_all(records):
        print(f"  {r.date} {r.vendor:14s} ${r.amount:>8,.2f}  -> {cat} ({conf:.2f})")

    rep = build_report(records, as_of)
    print()
    print(render_text(rep))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
