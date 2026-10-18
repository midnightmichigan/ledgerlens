"""Rule-based expense/income categorization for LedgerLens.

Uses a keyword knowledge base keyed on Schedule-C style categories.
No ML, no network: deterministic, explainable, honest confidence.
"""

from typing import Dict, List, Tuple
from .parse import Record

# category -> list of keyword phrases (lowercased, matched as substrings)
KB: Dict[str, List[str]] = {
    "Supplies": [
        "staples", "office depot", "office supplies", "paper", "ink", "toner",
        "notebook", "pens", "envelope", "shipping supplies", "packaging",
        "labels", "folders", "binder",
    ],
    "Meals": [
        "chipotle", "mcdonald", "restaurant", "coffee", "starbucks", "lunch",
        "dinner", "breakfast", "pizza", "catering", "doordash", "uber eats",
        "grubhub", "diner", "cafe", "bakery", "sandwich",
    ],
    "Travel": [
        "airline", "delta", "united", "southwest", "hotel", "airbnb",
        "motel", "flight", "boarding pass", "taxi", "lyft", "uber ride",
        "rental car", "parking", "toll", "amtrak", "train ticket",
    ],
    "Mileage": [
        "gas", "shell", "bp ", "speedway", "marathon", "meijer gas",
        "fuel", "mileage", "oil change", "tires", "auto repair",
    ],
    "Software": [
        "github", "adobe", "figma", "notion", "slack", "zoom", "dropbox",
        "google workspace", "microsoft 365", "domain", "hosting",
        "heroku", "vercel", "render.com", "digitalocean", "saas",
        "subscription", "canva", "grammarly",
    ],
    "Home Office": [
        "ikea desk", "office chair", "monitor", "keyboard", "mouse",
        "webcam", "headphones", "desk lamp", "home office", "printer",
    ],
    "Advertising": [
        "facebook ads", "google ads", "ad spend", "sponsored", "promoted",
        "flyers", "business cards", "logo", "branding", "mailchimp",
    ],
    "Professional Services": [
        "accountant", "bookkeeper", "lawyer", "attorney", "consulting",
        "legal", "tax prep", "cpa", "notary",
    ],
    "Utilities": [
        "electric", "consumers energy", "dte", "water bill", "internet",
        "comcast", "xfinity", "spectrum", "phone bill", "verizon",
        "t-mobile", "at&t",
    ],
    "Insurance": [
        "insurance", "liability", "workers comp", "premium",
    ],
    "Contract Labor": [
        "contractor", "subcontractor", "va ", "virtual assistant",
        "upwork", "fiverr", "1099", "freelancer payout",
    ],
    "Client Income": [
        "invoice", "client payment", "project fee", "retainer",
        "milestone", "consulting fee", "design work", "web design",
        "development", "copywriting",
    ],
}

# income-kind hint phrases force Client Income regardless of keyword hit
_INCOME_HINTS = ("invoice", "client payment", "received", "paid to me")


def categorize(rec: Record) -> Tuple[str, float, List[str]]:
    """Return (category, confidence, matched_keywords)."""
    text = f"{rec.vendor} {rec.description}".lower()

    if rec.kind == "income" or any(h in text for h in _INCOME_HINTS):
        hits = [kw for kw in KB["Client Income"] if kw in text]
        return ("Client Income", 0.9 if hits else 0.6, hits)

    if rec.kind == "transfer":
        return ("Transfers", 0.85, ["transfer-kind"])

    best_cat, best_hits = "Uncategorized", []
    for cat, keywords in KB.items():
        if cat == "Client Income":
            continue
        hits = [kw for kw in keywords if kw in text]
        if len(hits) > len(best_hits):
            best_cat, best_hits = cat, hits

    if not best_hits:
        return ("Uncategorized", 0.0, [])
    if len(best_hits) >= 2:
        confidence = 0.9
    else:
        # single-hit: check whether another category also claimed it
        rivals = [c for c, kws in KB.items()
                  if c not in ("Client Income", best_cat)
                  and any(kw in text for kw in kws)]
        confidence = 0.55 if rivals else 0.8
    return (best_cat, confidence, best_hits)


def categorize_all(records: List[Record]) -> List[Tuple[Record, str, float, List[str]]]:
    return [(r, *categorize(r)) for r in records]
