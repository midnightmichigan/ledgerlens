"""Record parsing for LedgerLens: CSV rows and loose plain-text receipts.

A Record is the unit everything else works on:
    date        datetime.date
    vendor      str
    description str
    amount      float (positive = money IN for income, money OUT for expenses)
    kind        'income' | 'expense' | 'transfer'
    due         datetime.date | None (invoices only)
    paid        bool
"""

import csv
import datetime
import io
import re
from dataclasses import dataclass, field
from typing import List, Optional

_AMT_RE = re.compile(r"\$\s*([0-9,]+(?:\.\d{1,2})?)")
_NUM_RE = re.compile(r"^\s*\$?\s*([0-9,]+(?:\.\d{1,2})?)\s*$")
_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


@dataclass
class Record:
    date: datetime.date
    vendor: str
    description: str
    amount: float
    kind: str = "expense"
    due: Optional[datetime.date] = None
    paid: bool = True
    raw: str = ""


def _parse_date(text: str, default: datetime.date) -> datetime.date:
    m = _DATE_RE.search(text or "")
    if not m:
        return default
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return default


def _parse_amount(text: str) -> Optional[float]:
    """Loose-text amount: requires an explicit $ sign."""
    m = _AMT_RE.search(text or "")
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _parse_number(text: str) -> Optional[float]:
    """CSV-cell amount: a whole cell that is just a number, $ optional."""
    m = _NUM_RE.match(text or "")
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def parse_csv(text: str, default_date: Optional[datetime.date] = None) -> List[Record]:
    """Parse a CSV of invoices/receipts.

    Header (case-insensitive, any order):
        date, vendor, description, amount, kind, due, paid
    Only date/vendor/description/amount are required.
    """
    default_date = default_date or datetime.date.today()
    out: List[Record] = []
    reader = csv.DictReader(io.StringIO(text.strip()))
    if reader.fieldnames is None:
        return out
    cols = {c.strip().lower(): c for c in reader.fieldnames}
    for row in reader:
        def cell(name: str) -> str:
            return (row.get(cols.get(name, ""), "") or "").strip()

        date = _parse_date(cell("date"), default_date)
        vendor = cell("vendor") or "Unknown"
        description = cell("description") or cell("vendor") or "receipt"
        amount = _parse_number(cell("amount"))
        if amount is None:
            continue  # row without money is not a record
        kind = (cell("kind") or "expense").lower()
        if kind not in ("income", "expense", "transfer"):
            kind = "expense"
        due = _parse_date(cell("due"), None) if cell("due") else None
        paid_txt = (cell("paid") or "yes").lower()
        paid = paid_txt not in ("no", "false", "0", "n", "unpaid")
        out.append(Record(date=date, vendor=vendor, description=description,
                          amount=amount, kind=kind, due=due, paid=paid,
                          raw=str(row)))
    return out


def parse_loose(text: str, default_date: Optional[datetime.date] = None) -> List[Record]:
    """Parse one record per line of loose plain text.

    Examples handled:
        "Staples office supplies $42.99"
        "2026-10-05, Chipotle client lunch $18.40"
        "Invoice #1042 Acme Corp web design work $1,200 due 2026-11-01"
    """
    default_date = default_date or datetime.date.today()
    out: List[Record] = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        amount = _parse_amount(line)
        if amount is None:
            continue
        date = _parse_date(line, default_date)
        lower = line.lower()
        kind = "income" if any(w in lower for w in ("invoice", "paid to me", "client payment", "received")) else "expense"
        # strip the amount/date tokens to find the vendor+description remainder
        cleaned = _AMT_RE.sub("", line)
        cleaned = _DATE_RE.sub("", cleaned).replace(",", " ")
        words = [w for w in cleaned.split() if w and not w.startswith("#")]
        vendor = words[0].title() if words else "Unknown"
        description = " ".join(words[1:]) or vendor
        due = None
        dm = re.search(r"due\s+(\d{4})-(\d{2})-(\d{2})", lower)
        if dm:
            try:
                due = datetime.date(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
            except ValueError:
                due = None
        out.append(Record(date=date, vendor=vendor, description=description,
                          amount=amount, kind=kind, due=due,
                          paid=due is None, raw=line))
    return out
