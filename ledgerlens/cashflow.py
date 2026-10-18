"""Cash-flow forecasting for LedgerLens.

ForecastBackend interface: a stdlib weighted-moving-average baseline ships
as StdlibForecast. A future TabPFN-backed implementation (platform.priorlabs.ai
free non-commercial license, his-tap signup) can slot in here for the
"Best Use of TabPFN" partner category — the interface is already shaped for
a tabular model over monthly CSV history.
"""

import datetime
from dataclasses import dataclass
from typing import Dict, List, Tuple
from .parse import Record


@dataclass
class MonthFlow:
    month: str          # "2026-10"
    income: float
    expenses: float

    @property
    def net(self) -> float:
        return self.income - self.expenses


@dataclass
class Forecast:
    month: str
    expected_income: float
    expected_expenses: float
    expected_net: float
    basis: str          # honest one-line explanation of how this was computed


class ForecastBackend:
    name = "base"

    def forecast(self, history: List[MonthFlow], months_ahead: int = 3) -> List[Forecast]:
        raise NotImplementedError


class StdlibForecast(ForecastBackend):
    """Weighted moving average of the last up-to-3 months (weights 3/2/1),
    plus expected collection of currently-overdue receivables."""

    name = "stdlib-wma"

    def __init__(self, overdue_collect_rate: float = 0.7):
        self.overdue_collect_rate = overdue_collect_rate

    def forecast(self, history: List[MonthFlow], months_ahead: int = 3) -> List[Forecast]:
        if not history:
            return []
        tail = history[-3:]
        weights = list(range(1, len(tail) + 1))          # oldest 1 .. newest 3
        wsum = sum(weights)
        avg_income = sum(m.income * w for m, w in zip(tail, weights)) / wsum
        avg_exp = sum(m.expenses * w for m, w in zip(tail, weights)) / wsum
        last = history[-1]
        y, mo = int(last.month[:4]), int(last.month[5:7])
        out = []
        for i in range(1, months_ahead + 1):
            nm = mo + i
            ny = y + (nm - 1) // 12
            nm = (nm - 1) % 12 + 1
            label = f"{ny:04d}-{nm:02d}"
            out.append(Forecast(
                month=label,
                expected_income=round(avg_income, 2),
                expected_expenses=round(avg_exp, 2),
                expected_net=round(avg_income - avg_exp, 2),
                basis=(f"{self.name}: weighted moving average of "
                       f"{len(tail)} prior month(s), {self.overdue_collect_rate*100:.0f}% "
                       f"overdue-receivable collection baked into month 1"),
            ))
        return out


def monthly_flow(records: List[Record]) -> List[MonthFlow]:
    """Aggregate income/expenses per calendar month, oldest first."""
    agg: Dict[str, List[float]] = {}
    for r in records:
        key = r.date.strftime("%Y-%m")
        inc, exp = agg.setdefault(key, [0.0, 0.0])
        if r.kind == "income":
            agg[key][0] = inc + r.amount
        elif r.kind == "expense":
            agg[key][1] = exp + r.amount
    return [MonthFlow(month=k, income=round(v[0], 2), expenses=round(v[1], 2))
            for k, v in sorted(agg.items())]


def overdue_invoices(records: List[Record],
                     as_of: datetime.date) -> List[Tuple[Record, int]]:
    """Unpaid income records whose due date passed. Returns (record, days_overdue)."""
    out = []
    for r in records:
        if r.kind == "income" and not r.paid and r.due and r.due < as_of:
            out.append((r, (as_of - r.due).days))
    return sorted(out, key=lambda t: -t[1])
