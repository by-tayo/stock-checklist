"""Shared paths, settings, SEC/Alpha Vantage clients and metric math.

The pure math lives here so tests/ can check it without touching the network.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CACHE = DATA / "cache"
OUTPUT = ROOT / "output"
DOCS = ROOT / "docs"

TICKER_MAP = CACHE / "company_tickers.json"
PRICES_CSV = DATA / "prices_manual.csv"
PRICE_CACHE = CACHE / "prices.json"
DEMO_MARKER = CACHE / "_DEMO_DATA_DO_NOT_TRUST.txt"

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
EDGAR_BROWSE = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
                "&CIK={cik:010d}&type=10-K&dateb=&owner=include&count=10")
ALPHA_URL = "https://www.alphavantage.co/query"

# SEC asks for 10 requests per second at most; we stay well under.
SEC_PAUSE_SECONDS = 0.2

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass


# ---------------------------------------------------------------- settings

def setting(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def setting_float(name: str, default: float) -> float:
    raw = setting(name)
    if raw == "":
        return default
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        fail(f"{name} in .env must be a number, got {raw!r}")
    return default


def fail(message: str) -> None:
    print(f"\n[ERROR] {message}\n")
    sys.exit(1)


def info(message: str) -> None:
    print(f"[OK] {message}")


def warn(message: str) -> None:
    print(f"[WARN] {message}")


def is_demo() -> bool:
    return DEMO_MARKER.exists()


def demo_banner() -> None:
    if is_demo():
        print("=" * 72)
        print("DEMO DATA: these companies are invented. Every number below is fake.")
        print("Run 01_fetch_company.py with real tickers for real filings.")
        print("=" * 72)


def sec_headers() -> dict:
    """The SEC requires a User-Agent naming you and a contact email."""
    contact = setting("SEC_USER_AGENT")
    if not contact or "@" not in contact:
        fail("SEC_USER_AGENT in .env must be your name and email, for example:\n"
             "  SEC_USER_AGENT=Tayo Ortiz you@example.com\n"
             "The SEC rejects automated requests that do not identify themselves.")
    return {"User-Agent": contact, "Accept-Encoding": "gzip, deflate"}


# ---------------------------------------------------------------- network

def get_json(url: str, headers: dict | None = None, params: dict | None = None,
             retries: int = 3) -> dict:
    import requests

    last = ""
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=headers or {}, params=params or {},
                                    timeout=30)
        except Exception as exc:
            last = str(exc)
            time.sleep(2 * attempt)
            continue
        if response.status_code == 403:
            fail(f"403 from {url}\nFor SEC URLs this usually means the User-Agent "
                 "header is missing or does not include a contact email.")
        if response.status_code == 404:
            return {}
        if response.status_code == 429:
            warn(f"Rate limited; waiting {5 * attempt}s")
            time.sleep(5 * attempt)
            continue
        if response.status_code != 200:
            last = f"HTTP {response.status_code}: {response.text[:200]}"
            time.sleep(2 * attempt)
            continue
        try:
            return response.json()
        except ValueError:
            fail(f"{url} did not return JSON. First 200 characters:\n{response.text[:200]}")
    fail(f"Could not fetch {url} after {retries} tries. Last error: {last}")
    return {}


def load_ticker_map(refresh: bool = False) -> dict[str, dict]:
    """ticker -> {cik, title}, from the SEC's public list."""
    CACHE.mkdir(parents=True, exist_ok=True)
    if TICKER_MAP.exists() and not refresh:
        raw = json.loads(TICKER_MAP.read_text(encoding="utf-8"))
    else:
        raw = get_json(SEC_TICKERS_URL, headers=sec_headers())
        if not raw:
            fail("Could not download the SEC ticker list.")
        TICKER_MAP.write_text(json.dumps(raw), encoding="utf-8")
    mapping = {}
    for entry in raw.values():
        mapping[str(entry["ticker"]).upper()] = {"cik": int(entry["cik_str"]),
                                                 "title": entry["title"]}
    return mapping


def facts_path(ticker: str) -> Path:
    return CACHE / f"facts_{ticker.upper()}.json"


def fetch_company_facts(ticker: str, cik: int) -> dict:
    payload = get_json(SEC_FACTS_URL.format(cik=cik), headers=sec_headers())
    time.sleep(SEC_PAUSE_SECONDS)
    if not payload:
        fail(f"No XBRL facts for {ticker} (CIK {cik}). Foreign filers and very small "
             "companies often have none.")
    return payload


def fetch_price(ticker: str) -> float | None:
    """Latest price from Alpha Vantage, cached for the day. None if unavailable."""
    import datetime as dt

    CACHE.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    cached = json.loads(PRICE_CACHE.read_text(encoding="utf-8")) if PRICE_CACHE.exists() else {}
    hit = cached.get(ticker.upper())
    if hit and hit.get("date") == today:
        return float(hit["price"])

    key = setting("ALPHAVANTAGE_API_KEY")
    if not key or key.lower().startswith("paste"):
        return None
    payload = get_json(ALPHA_URL, params={"function": "GLOBAL_QUOTE",
                                          "symbol": ticker.upper(), "apikey": key})
    quote = payload.get("Global Quote") or {}
    note = payload.get("Note") or payload.get("Information")
    if note:
        warn(f"Alpha Vantage says: {note[:160]}")
        return None
    try:
        price = float(quote.get("05. price"))
    except (TypeError, ValueError):
        return None
    cached[ticker.upper()] = {"price": price, "date": today}
    PRICE_CACHE.write_text(json.dumps(cached, indent=2), encoding="utf-8")
    return price


def manual_prices() -> dict[str, float]:
    if not PRICES_CSV.exists():
        return {}
    frame = pd.read_csv(PRICES_CSV)
    return {str(r["ticker"]).upper(): float(r["price"]) for _, r in frame.iterrows()
            if pd.notna(r.get("price"))}


def price_for(ticker: str) -> tuple[float | None, str]:
    """(price, where it came from)."""
    manual = manual_prices()
    if ticker.upper() in manual:
        return manual[ticker.upper()], "manual (data/prices_manual.csv)"
    price = fetch_price(ticker)
    if price is not None:
        return price, "Alpha Vantage"
    return None, "unavailable"


# ---------------------------------------------------------------- XBRL

# Each metric lists tags in preference order: filers tag the same idea differently.
FLOW_TAGS = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax",
                "RevenueFromContractWithCustomerIncludingAssessedTax",
                "Revenues", "SalesRevenueNet", "SalesRevenueGoodsNet"],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities",
                            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment",
              "PaymentsToAcquireProductiveAssets"],
    "dividends_paid": ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends"],
    "interest_expense": ["InterestExpense", "InterestIncomeExpenseNet"],
}

INSTANT_TAGS = {
    "assets": ["Assets"],
    "liabilities": ["Liabilities"],
    "equity": ["StockholdersEquity",
               "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue",
             "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "long_term_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "short_term_debt": ["LongTermDebtCurrent", "ShortTermBorrowings",
                        "OtherShortTermBorrowings"],
    "preferred_stock": ["PreferredStockValue"],
}

PER_SHARE_TAGS = {
    "eps_diluted": ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"],
    "dividends_per_share": ["CommonStockDividendsPerShareDeclared",
                            "CommonStockDividendsPerShareCashPaid"],
}

SHARE_TAGS = {
    "diluted_shares": ["WeightedAverageNumberOfDilutedSharesOutstanding",
                       "WeightedAverageNumberOfSharesOutstandingBasic"],
}

ANNUAL_FORMS = ("10-K",)


def _entries(facts: dict, tag: str) -> list[dict]:
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    if tag not in us_gaap:
        return []
    out = []
    for unit_rows in us_gaap[tag].get("units", {}).values():
        out.extend(unit_rows)
    return out


def _merge_tag_series(per_tag: list[pd.Series]) -> pd.Series:
    """Union series from several tags, in preference order.

    Filers sometimes switch which tag they use for the same concept partway through
    their history (NVIDIA moved revenue from RevenueFromContractWithCustomer... back
    to the older Revenues tag, for example). Taking only the first tag with any data
    would silently drop the years reported under a later tag, so instead every tag's
    years go in and, where two tags cover the same year, the earlier (preferred) tag
    wins.
    """
    series = [s for s in per_tag if not s.empty]
    if not series:
        return pd.Series(dtype=float)
    combined = series[0]
    for s in series[1:]:
        combined = combined.combine_first(s)
    return combined.sort_index()


def annual_flow(facts: dict, tags: list[str]) -> pd.Series:
    """Full-year values from 10-K filings, keyed by fiscal year."""
    per_tag = []
    for tag in tags:
        rows = []
        for row in _entries(facts, tag):
            if not str(row.get("form", "")).startswith(ANNUAL_FORMS):
                continue
            start, end = row.get("start"), row.get("end")
            if not start or not end:
                continue
            length = (pd.Timestamp(end) - pd.Timestamp(start)).days
            if not 330 <= length <= 400:  # a fiscal year, not a quarter
                continue
            rows.append({"fy": int(row.get("fy") or pd.Timestamp(end).year),
                         "end": end, "val": row["val"], "accn": row.get("accn", "")})
        if rows:
            frame = pd.DataFrame(rows).sort_values(["fy", "end", "accn"])
            # Later filings restate earlier years; keep the most recent statement.
            per_tag.append(frame.groupby("fy")["val"].last())
        else:
            per_tag.append(pd.Series(dtype=float))
    return _merge_tag_series(per_tag)


def annual_instant(facts: dict, tags: list[str]) -> pd.Series:
    """Balance-sheet values at fiscal year end, keyed by fiscal year."""
    per_tag = []
    for tag in tags:
        rows = []
        for row in _entries(facts, tag):
            if not str(row.get("form", "")).startswith(ANNUAL_FORMS):
                continue
            if row.get("start"):  # instants have no start date
                continue
            end = row.get("end")
            if not end:
                continue
            rows.append({"fy": int(row.get("fy") or pd.Timestamp(end).year),
                         "end": end, "val": row["val"], "accn": row.get("accn", "")})
        if rows:
            frame = pd.DataFrame(rows).sort_values(["fy", "end", "accn"])
            per_tag.append(frame.groupby("fy")["val"].last())
        else:
            per_tag.append(pd.Series(dtype=float))
    return _merge_tag_series(per_tag)


# ---------------------------------------------------------------- metrics

def safe_divide(numerator, denominator):
    """Division that returns NaN instead of exploding on zero or missing values."""
    if numerator is None or denominator is None:
        return float("nan")
    try:
        numerator = float(numerator)
        denominator = float(denominator)
    except (TypeError, ValueError):
        return float("nan")
    if denominator == 0 or pd.isna(denominator) or pd.isna(numerator):
        return float("nan")
    return numerator / denominator


def cagr(first: float, last: float, years: int) -> float:
    """Compound annual growth rate. NaN when the sign makes it meaningless."""
    if years <= 0 or first is None or last is None:
        return float("nan")
    if pd.isna(first) or pd.isna(last) or first <= 0 or last <= 0:
        return float("nan")
    return (last / first) ** (1 / years) - 1


def derive_metrics(table: pd.DataFrame) -> pd.DataFrame:
    """Add ratio columns to a per-year fundamentals table.

    Filers omit tags all the time, so every column is looked up through col(),
    which supplies an all-missing column rather than raising.
    """
    out = table.copy()

    def col(name: str) -> pd.Series:
        if name in out:
            return pd.to_numeric(out[name], errors="coerce")
        return pd.Series([float("nan")] * len(out), index=out.index, dtype=float)

    def safe(name: str) -> pd.Series:
        """Same, but missing counts as zero (for sums, not for ratios)."""
        return col(name).fillna(0)

    revenue = col("revenue")
    equity = col("equity").replace(0, float("nan"))

    out["total_debt"] = safe("long_term_debt") + safe("short_term_debt")
    out["net_debt"] = out["total_debt"] - safe("cash")
    out["free_cash_flow"] = col("operating_cash_flow") - col("capex")
    out["gross_margin"] = col("gross_profit") / revenue
    out["operating_margin"] = col("operating_income") / revenue
    out["net_margin"] = col("net_income") / revenue
    out["fcf_margin"] = out["free_cash_flow"] / revenue
    out["return_on_equity"] = col("net_income") / equity
    invested = (equity.fillna(0) + out["total_debt"]).replace(0, float("nan"))
    out["return_on_invested_capital"] = col("operating_income") / invested
    out["debt_to_equity"] = out["total_debt"] / equity
    out["revenue_growth"] = revenue.pct_change()
    out["payout_ratio"] = col("dividends_per_share") / col("eps_diluted").replace(0, float("nan"))
    out["cash_conversion"] = col("operating_cash_flow") / col("net_income").replace(0, float("nan"))
    return out.replace([float("inf"), float("-inf")], float("nan"))


def classify_size(market_cap: float) -> str:
    """Conventional US buckets. Conventions, not rules - see docs/methodology.md."""
    if market_cap is None or pd.isna(market_cap):
        return "unknown"
    billions = market_cap / 1e9
    if billions >= 200:
        return "mega cap"
    if billions >= 10:
        return "large cap"
    if billions >= 2:
        return "mid cap"
    if billions >= 0.3:
        return "small cap"
    return "micro cap"


def classify_style(revenue_cagr: float, dividend_yield: float,
                   growth_threshold: float = 0.10,
                   yield_threshold: float = 0.03) -> str:
    """A rough label, not a verdict."""
    fast = revenue_cagr is not None and not pd.isna(revenue_cagr) \
        and revenue_cagr >= growth_threshold
    pays = dividend_yield is not None and not pd.isna(dividend_yield) \
        and dividend_yield >= yield_threshold
    if fast and pays:
        return "growth with income"
    if fast:
        return "growth"
    if pays:
        return "income"
    return "neither clearly growth nor income"


def money(value: float) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    for cutoff, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(value) >= cutoff:
            return f"${value / cutoff:,.2f}{suffix}"
    return f"${value:,.0f}"


def percent(value: float, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value * 100:.{digits}f}%"


def ratio(value: float, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value:.{digits}f}"
