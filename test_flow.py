#!/usr/bin/env python3
"""test_flow.py — LedgerLens full flow checks. Run: python3 test_flow.py"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ledgerlens.parse import Record, parse_csv, parse_loose
from ledgerlens.categorize import categorize, categorize_all, KB
from ledgerlens.cashflow import (
    Forecast, ForecastBackend, MonthFlow, StdlibForecast,
    monthly_flow, overdue_invoices,
)
from ledgerlens.report import build_report, render_text
from demo import FIXTURE_CSV, FIXTURE_LOOSE
from ledgerlens.webdemo import (
    esc, money, conf_bar, analyze_records, report_page, index_page, HISTORY,
)

CHECKS = []


def check(name, fn):
    try:
        fn()
        CHECKS.append((name, True, ""))
    except AssertionError as e:
        CHECKS.append((name, False, str(e) or "assert failed"))
    except Exception as e:  # noqa: BLE001
        CHECKS.append((name, False, f"{type(e).__name__}: {e}"))


def r(**kw):
    base = dict(date=datetime.date(2026, 10, 1), vendor="V", description="d",
                amount=10.0, kind="expense")
    base.update(kw)
    return Record(**base)


# --- parse_csv ---
def t_csv_basic():
    recs = parse_csv("date,vendor,description,amount,kind,due,paid\n"
                     "2026-09-01,Staples,paper,42.99,expense,,yes")
    assert len(recs) == 1, recs
    x = recs[0]
    assert x.date == datetime.date(2026, 9, 1)
    assert x.amount == 42.99 and x.kind == "expense" and x.paid

def t_csv_income_overdue():
    recs = parse_csv("date,vendor,description,amount,kind,due,paid\n"
                     "2026-08-12,Brightside,Invoice #1042 copywriting,850,income,2026-09-11,no")
    x = recs[0]
    assert x.kind == "income" and not x.paid
    assert x.due == datetime.date(2026, 9, 11)

def t_csv_skips_moneyless_row():
    recs = parse_csv("date,vendor,description,amount\n2026-09-01,Staples,paper,")
    assert recs == []

def t_csv_dollar_comma_amount():
    recs = parse_csv('date,vendor,description,amount\n2026-09-01,Acme,retainer,"$1,200.50"')
    assert recs and recs[0].amount == 1200.50, recs

def t_csv_plain_number_amount():
    recs = parse_csv("date,vendor,description,amount\n2026-09-01,Acme,retainer,850")
    assert recs and recs[0].amount == 850.0, recs

def t_csv_unknown_kind_defaults_expense():
    recs = parse_csv("date,vendor,description,amount,kind\n2026-09-01,Staples,paper,9.99,weird")
    assert recs[0].kind == "expense"

# --- parse_loose ---
def t_loose_basic():
    recs = parse_loose("Staples office supplies $42.99")
    assert len(recs) == 1
    assert recs[0].amount == 42.99 and recs[0].vendor == "Staples"

def t_loose_date_and_due():
    recs = parse_loose("Invoice #1042 Acme Corp web design work $1200 due 2026-11-01")
    assert len(recs) == 1
    x = recs[0]
    assert x.kind == "income" and x.amount == 1200.0
    assert x.due == datetime.date(2026, 11, 1) and not x.paid

def t_loose_skips_non_money_lines():
    recs = parse_loose("hello world\nno price here\nStaples pens $4.00")
    assert len(recs) == 1

# --- categorize ---
def t_cat_meals():
    cat, conf, hits = categorize(r(vendor="Chipotle", description="client lunch meeting"))
    assert cat == "Meals", (cat, hits)
    assert conf >= 0.8

def t_cat_software():
    cat, conf, hits = categorize(r(vendor="DigitalOcean", description="GPU droplet hosting"))
    assert cat == "Software", (cat, hits)

def t_cat_mileage():
    cat, conf, _ = categorize(r(vendor="Shell", description="gas to client site"))
    assert cat == "Mileage", cat

def t_cat_income_forces_client_income():
    cat, conf, _ = categorize(r(vendor="Acme", description="retainer", kind="income", amount=1500.0))
    assert cat == "Client Income"

def t_cat_transfer():
    cat, conf, _ = categorize(r(kind="transfer", description="savings transfer"))
    assert cat == "Transfers"

def t_cat_uncategorized_zero_conf():
    cat, conf, hits = categorize(r(vendor="ZZZqzx", description="mystery widget blorp"))
    assert cat == "Uncategorized" and conf == 0.0 and hits == []

def t_cat_ambiguous_low_conf():
    # "Apple" alone hits nothing specific; a single vague hit with rivals lowers confidence
    cat, conf, hits = categorize(r(vendor="Apple", description="coffee"))
    assert cat == "Meals" and conf < 0.9, (cat, conf)

def t_cat_kb_nonempty_all_categories():
    for cat, kws in KB.items():
        assert kws, f"{cat} has no keywords"

# --- cashflow ---
def t_monthly_flow_order_and_net():
    recs = [
        r(date=datetime.date(2026, 9, 1), kind="income", amount=1000.0),
        r(date=datetime.date(2026, 9, 2), kind="expense", amount=300.0),
        r(date=datetime.date(2026, 8, 5), kind="income", amount=500.0),
    ]
    mf = monthly_flow(recs)
    assert [m.month for m in mf] == ["2026-08", "2026-09"]
    assert mf[1].income == 1000.0 and mf[1].expenses == 300.0 and mf[1].net == 700.0

def t_overdue_sorted_by_days():
    recs = [
        r(kind="income", amount=100.0, paid=False, due=datetime.date(2026, 9, 1), vendor="A"),
        r(kind="income", amount=200.0, paid=False, due=datetime.date(2026, 10, 1), vendor="B"),
        r(kind="income", amount=300.0, paid=True, due=datetime.date(2026, 9, 1), vendor="C"),
    ]
    od = overdue_invoices(recs, datetime.date(2026, 10, 12))
    assert [x[0].vendor for x in od] == ["A", "B"], od
    assert od[0][1] == 41 and od[1][1] == 11

def t_forecast_shape_and_basis():
    hist = [MonthFlow("2026-07", 1000, 400), MonthFlow("2026-08", 2000, 600)]
    fc = StdlibForecast().forecast(hist, 2)
    assert len(fc) == 2
    assert fc[0].month == "2026-09" and fc[1].month == "2026-10"
    # weighted (1*1000+2*2000)/3 = 1666.67 income; (1*400+2*600)/3 = 533.33 exp
    assert abs(fc[0].expected_income - 1666.67) < 0.02
    assert abs(fc[0].expected_expenses - 533.33) < 0.02
    assert abs(fc[0].expected_net - 1133.34) < 0.02
    assert "stdlib-wma" in fc[0].basis

def t_forecast_empty_history():
    assert StdlibForecast().forecast([], 3) == []

def t_forecast_backend_interface():
    assert isinstance(StdlibForecast(), ForecastBackend)
    assert hasattr(StdlibForecast(), "name")

# --- report ---
def t_report_totals_and_overdue():
    recs = parse_csv(FIXTURE_CSV)
    rep = build_report(recs, datetime.date(2026, 10, 12))
    # income: 1500+850+1500+600+1500 = 5950; expenses: 42.99+18.40+24+38.15+10+65+21.75+289 = 509.29
    assert abs(rep.total_income - 5950.0) < 0.01, rep.total_income
    assert abs(rep.total_expenses - 509.29) < 0.01, rep.total_expenses
    assert abs(rep.net - (5950.0 - 509.29)) < 0.01
    assert len(rep.overdue) == 2  # #1042 (31d) + #1043 (10d); #1045 not due yet
    assert any("Brightside" in l for l in rep.overdue)
    assert any("URGENT" in a for a in rep.actions)  # #1042 is 31d overdue

def t_report_uncategorized_action():
    recs = [r(vendor="ZZZqzx", description="mystery widget blorp")]
    rep = build_report(recs, datetime.date(2026, 10, 12))
    assert rep.uncategorized_count == 1
    assert any("Uncategorized" in a for a in rep.actions)

def t_report_cash_negative_action():
    recs = [r(kind="expense", amount=500.0, description="staples paper"),
            r(kind="income", amount=100.0, description="invoice", vendor="C")]
    rep = build_report(recs, datetime.date(2026, 10, 12))
    assert any("Cash-negative" in a for a in rep.actions)

def t_render_text_contains_sections():
    rep = build_report(parse_csv(FIXTURE_CSV), datetime.date(2026, 10, 12))
    txt = render_text(rep)
    for needle in ("category totals", "overdue invoices", "3-month forecast", "actions"):
        assert needle in txt, needle

# --- demo end-to-end ---
def t_demo_runs():
    import demo
    assert demo.main() == 0


# --- webdemo ---
def t_web_esc_escapes_html():
    assert esc("<script>alert(1)</script>") == "&lt;script&gt;alert(1)&lt;/script&gt;"
    assert esc('a"b') == "a&quot;b"

def t_web_money_format():
    assert money(1500) == "$1,500.00"
    assert money(-42.5) == "$-42.50"

def t_web_conf_bar_bounds():
    low = conf_bar(0.1)
    high = conf_bar(0.95)
    assert "10%" in low and "95%" in high
    assert "c62828" in low and "2e7d32" in high

def t_web_analyze_records_fixture():
    recs, note = analyze_records(FIXTURE_CSV, datetime.date(2026, 10, 12))
    assert note is None and len(recs) == 13, (len(recs), note)

def t_web_analyze_records_nothing_parsed():
    recs, note = analyze_records("hello there, no money here", datetime.date(2026, 10, 12))
    assert recs == [] and note

def t_web_report_page_sections():
    recs, _ = analyze_records(FIXTURE_CSV, datetime.date(2026, 10, 12))
    n0 = len(HISTORY)
    html_out = report_page(recs, datetime.date(2026, 10, 12), "SYNTHETIC FIXTURE")
    for section in ("Category totals", "Overdue-invoice radar", "cash-flow forecast",
                    "Action items", "Record-by-record", "SYNTHETIC FIXTURE"):
        assert section in html_out, section
    assert len(HISTORY) == n0 + 1 and HISTORY[-1]["records"] == 13

def t_web_report_page_escapes_xss():
    poisoned = ("date,vendor,description,amount,kind,due,paid\n"
                "2026-10-01,<script>alert('x')</script>,evil,9.99,expense,,")
    recs, _ = analyze_records(poisoned, datetime.date(2026, 10, 12))
    html_out = report_page(recs, datetime.date(2026, 10, 12), "test")
    assert "<script>" not in html_out
    assert "&lt;script&gt;" in html_out

def t_web_index_page_form():
    page_html = index_page()
    assert "form method='post' action='/analyze'" in page_html
    assert "synthetic fixture" in page_html


CHECKS_ORDER = [
    ("csv basic", t_csv_basic),
    ("csv income overdue", t_csv_income_overdue),
    ("csv skips moneyless row", t_csv_skips_moneyless_row),
    ("csv dollar-comma amount", t_csv_dollar_comma_amount),
    ("csv plain number amount", t_csv_plain_number_amount),
    ("csv unknown kind defaults expense", t_csv_unknown_kind_defaults_expense),
    ("loose basic", t_loose_basic),
    ("loose date and due", t_loose_date_and_due),
    ("loose skips non-money lines", t_loose_skips_non_money_lines),
    ("cat meals", t_cat_meals),
    ("cat software", t_cat_software),
    ("cat mileage", t_cat_mileage),
    ("cat income forces client income", t_cat_income_forces_client_income),
    ("cat transfer", t_cat_transfer),
    ("cat uncategorized zero conf", t_cat_uncategorized_zero_conf),
    ("cat ambiguous low conf", t_cat_ambiguous_low_conf),
    ("cat kb nonempty", t_cat_kb_nonempty_all_categories),
    ("monthly flow order and net", t_monthly_flow_order_and_net),
    ("overdue sorted by days", t_overdue_sorted_by_days),
    ("forecast shape and basis", t_forecast_shape_and_basis),
    ("forecast empty history", t_forecast_empty_history),
    ("forecast backend interface", t_forecast_backend_interface),
    ("report totals and overdue", t_report_totals_and_overdue),
    ("report uncategorized action", t_report_uncategorized_action),
    ("report cash-negative action", t_report_cash_negative_action),
    ("render text sections", t_render_text_contains_sections),
    ("demo runs end-to-end", t_demo_runs),
    ("web esc escapes html", t_web_esc_escapes_html),
    ("web money format", t_web_money_format),
    ("web conf bar bounds", t_web_conf_bar_bounds),
    ("web analyze records fixture", t_web_analyze_records_fixture),
    ("web analyze records nothing parsed", t_web_analyze_records_nothing_parsed),
    ("web report page sections", t_web_report_page_sections),
    ("web report page escapes xss", t_web_report_page_escapes_xss),
    ("web index page form", t_web_index_page_form),
]

if __name__ == "__main__":
    for name, fn in CHECKS_ORDER:
        check(name, fn)
    passed = sum(1 for _, ok, _ in CHECKS if ok)
    total = len(CHECKS)
    print(f"\n{passed}/{total} checks passed")
    for name, ok, err in CHECKS:
        if not ok:
            print(f"  FAIL: {name}: {err}")
    sys.exit(0 if passed == total else 1)
