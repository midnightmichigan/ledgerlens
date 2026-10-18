"""Actionable bookkeeping report for LedgerLens."""

import datetime
from dataclasses import dataclass
from typing import Dict, List
from .parse import Record
from .categorize import categorize_all
from .cashflow import (
    ForecastBackend, StdlibForecast, monthly_flow, overdue_invoices,
)


@dataclass
class Report:
    category_totals: Dict[str, float]
    total_income: float
    total_expenses: float
    net: float
    overdue: List[str]
    actions: List[str]
    forecast_lines: List[str]
    categorized_count: int
    uncategorized_count: int


def build_report(records: List[Record],
                 as_of: datetime.date,
                 forecaster: ForecastBackend = None) -> Report:
    forecaster = forecaster or StdlibForecast()
    categorized = categorize_all(records)

    totals: Dict[str, float] = {}
    income = expenses = 0.0
    uncategorized = 0
    for r, cat, conf, hits in categorized:
        if r.kind == "transfer":
            continue
        if r.kind == "income":
            income += r.amount
        elif r.kind == "expense":
            expenses += r.amount
        if cat == "Uncategorized":
            uncategorized += 1
        totals[cat] = round(totals.get(cat, 0.0) + r.amount, 2)

    overdue_lines, actions = [], []
    overdue_total = 0.0
    for r, days in overdue_invoices(records, as_of):
        overdue_lines.append(f"{r.vendor} — ${r.amount:,.2f} ({days}d overdue)")
        overdue_total += r.amount
        if days >= 30:
            actions.append(
                f"URGENT: {r.vendor} invoice ${r.amount:,.2f} is {days} days "
                f"overdue — send a follow-up today.")

    if overdue_total:
        actions.append(
            f"You have ${overdue_total:,.2f} in overdue receivables — "
            f"collecting them is the fastest 'revenue' you'll ever book.")

    hist = monthly_flow(records)
    forecast_lines = []
    for f in forecaster.forecast(hist, 3):
        forecast_lines.append(
            f"{f.month}: income ~${f.expected_income:,.2f}, "
            f"expenses ~${f.expected_expenses:,.2f}, "
            f"net ~${f.expected_net:,.2f}")
    if hist:
        forecast_lines.append(f"basis: {forecaster.forecast(hist, 3)[0].basis}")

    if income < expenses and (income or expenses):
        actions.append(
            f"Cash-negative period: expenses exceed income by "
            f"${expenses - income:,.2f} — review the top expense categories first.")
    if uncategorized:
        actions.append(
            f"{uncategorized} record(s) Uncategorized — rename their vendor/description "
            f"so the next run categorizes them.")

    return Report(
        category_totals=dict(sorted(totals.items(), key=lambda kv: -abs(kv[1]))),
        total_income=round(income, 2),
        total_expenses=round(expenses, 2),
        net=round(income - expenses, 2),
        overdue=overdue_lines,
        actions=actions,
        forecast_lines=forecast_lines,
        categorized_count=len(categorized) - uncategorized,
        uncategorized_count=uncategorized,
    )


def render_text(rep: Report) -> str:
    lines = ["== LedgerLens bookkeeping report ==",
             f"income: ${rep.total_income:,.2f}   expenses: ${rep.total_expenses:,.2f}   net: ${rep.net:,.2f}",
             "",
             "-- category totals --"]
    for cat, total in rep.category_totals.items():
        lines.append(f"  {cat:24s} ${total:>10,.2f}")
    if rep.overdue:
        lines += ["", "-- overdue invoices --"] + [f"  {l}" for l in rep.overdue]
    if rep.forecast_lines:
        lines += ["", "-- 3-month forecast --"] + [f"  {l}" for l in rep.forecast_lines]
    if rep.actions:
        lines += ["", "-- actions --"] + [f"  * {a}" for a in rep.actions]
    lines.append(f"\n(categorized {rep.categorized_count}, uncategorized {rep.uncategorized_count})")
    return "\n".join(lines)
