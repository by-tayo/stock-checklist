"""Step 2: turn raw XBRL facts into a year-by-year table of fundamentals.

Run:  python 02_metrics.py

Writes output/<TICKER>_fundamentals.csv for each company and prints the subject's
recent years so you can sanity-check the numbers against the actual 10-K.
"""

from __future__ import annotations

import json

import pandas as pd

from sc_common import (CACHE, FLOW_TAGS, INSTANT_TAGS, OUTPUT, PER_SHARE_TAGS,
                       SHARE_TAGS, annual_flow, annual_instant, demo_banner,
                       derive_metrics, facts_path, fail, info, money, percent, ratio,
                       warn)

INDEX_PATH = CACHE / "company_index.json"


def build_table(facts: dict) -> pd.DataFrame:
    columns = {}
    for name, tags in FLOW_TAGS.items():
        columns[name] = annual_flow(facts, tags)
    for name, tags in INSTANT_TAGS.items():
        columns[name] = annual_instant(facts, tags)
    for name, tags in PER_SHARE_TAGS.items():
        columns[name] = annual_flow(facts, tags)
    for name, tags in SHARE_TAGS.items():
        columns[name] = annual_flow(facts, tags)
    table = pd.DataFrame(columns)
    table.index.name = "fiscal_year"
    return table.sort_index()


def main() -> None:
    demo_banner()
    if not INDEX_PATH.exists():
        fail("No companies fetched yet. Run:  python 01_fetch_company.py TICKER")
    OUTPUT.mkdir(exist_ok=True)
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))

    for ticker, meta in index["companies"].items():
        path = facts_path(ticker)
        if not path.exists():
            fail(f"Missing cached filings for {ticker}. Re-run 01_fetch_company.py.")
        facts = json.loads(path.read_text(encoding="utf-8"))
        table = build_table(facts)
        if table.empty or "revenue" not in table or table["revenue"].dropna().empty:
            fail(f"{ticker}: no annual revenue found in the filings. The company may "
                 "tag revenue with a concept this tool does not know. "
                 "See docs/methodology.md for how to add a tag.")
        table = derive_metrics(table)
        table.to_csv(OUTPUT / f"{ticker}_fundamentals.csv")
        years = table["revenue"].dropna()
        missing = [c for c in ("gross_profit", "operating_income", "equity",
                               "operating_cash_flow")
                   if c not in table or table[c].dropna().empty]
        info(f"{ticker}: {len(years)} fiscal years ({years.index.min()}-{years.index.max()})")
        if missing:
            warn(f"{ticker}: no data for {', '.join(missing)}. Those ratios will be "
                 "blank. Common for financial companies and for filers using "
                 "different tags.")

    subject = index["subject"]
    table = pd.read_csv(OUTPUT / f"{subject}_fundamentals.csv", index_col="fiscal_year")
    recent = table.tail(5)
    print(f"\n{subject} - last five fiscal years\n")
    header = (f"{'Year':<7}{'Revenue':>12}{'Op margin':>11}{'Net margin':>12}"
              f"{'ROE':>9}{'FCF':>12}{'Debt/Eq':>9}")
    print(header)
    print("-" * len(header))
    for year, row in recent.iterrows():
        print(f"{int(year):<7}{money(row.get('revenue')):>12}"
              f"{percent(row.get('operating_margin')):>11}"
              f"{percent(row.get('net_margin')):>12}"
              f"{percent(row.get('return_on_equity')):>9}"
              f"{money(row.get('free_cash_flow')):>12}"
              f"{ratio(row.get('debt_to_equity'), 2):>9}")
    print("-" * len(header))
    print("\nCHECKPOINT: open the company's latest 10-K and check one revenue figure "
          "against this table. XBRL tags vary between filers, and a mismatch here is "
          "the one error that would quietly wreck everything downstream.")
    print("Then run:  python 03_tearsheet.py")


if __name__ == "__main__":
    main()
