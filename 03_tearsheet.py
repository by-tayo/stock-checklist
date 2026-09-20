"""Step 3: build the one-page tear sheet for the subject company.

Run:  python 03_tearsheet.py

Writes output/<TICKER>_tearsheet.md and output/<TICKER>_history.png.

The tear sheet answers the measurable half of the investment checklist and points
at the filing sections for the half no tool can answer.
"""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from sc_common import (CACHE, OUTPUT, cagr, classify_size, classify_style, demo_banner,
                       fail, info, is_demo, money, percent, ratio, safe_divide,
                       setting_float)

INDEX_PATH = CACHE / "company_index.json"
LINE = "#2a78d6"
BAR = "#eb6834"
INK = "#1f1f1e"
MUTED = "#6b6a63"
GRID = "#e4e3dc"


def flags(table: pd.DataFrame, price: float | None, meta: dict) -> list[str]:
    """Things worth a second look. Not verdicts."""
    out = []
    latest = table.iloc[-1]
    years = table.tail(5)

    if price is not None and price < 5:
        out.append("Trades under $5. Below that, and especially off-exchange, a stock "
                   "meets the SEC's penny-stock definition, where disclosure is thin "
                   "and spreads are wide.")
    exchange = str(meta.get("exchange", ""))
    if exchange and "not listed" in exchange.lower():
        out.append("Not listed on a major exchange. Reporting obligations are lighter "
                   "and liquidity is usually poor.")
    if pd.notna(latest.get("net_income")) and latest["net_income"] < 0:
        out.append("Lost money in the most recent year.")
    if (years["revenue_growth"].dropna() < 0).sum() >= 3:
        out.append("Revenue fell in at least three of the last five years.")
    if pd.notna(latest.get("debt_to_equity")) and latest["debt_to_equity"] > 2:
        out.append(f"Debt is {ratio(latest['debt_to_equity'], 1)}x equity. High "
                   "leverage magnifies both directions.")
    if pd.notna(latest.get("equity")) and latest["equity"] < 0:
        out.append("Negative book equity. Often buybacks or accumulated losses; worth "
                   "understanding which.")
    conversion = years["cash_conversion"].dropna()
    if not conversion.empty and conversion.mean() < 0.8:
        out.append("Operating cash flow runs below reported net income. Earnings "
                   "quality is worth checking in the cash flow statement.")
    payout = years["payout_ratio"].dropna()
    if not payout.empty and payout.iloc[-1] > 1:
        out.append("Dividends exceeded earnings last year, so the payout is not "
                   "covered by profit.")
    shares = table["diluted_shares"].dropna()
    if len(shares) >= 5 and shares.iloc[-1] > shares.iloc[-5] * 1.10:
        out.append("Share count grew more than 10% over five years, diluting existing "
                   "holders.")
    if str(meta.get("sic", "")).startswith(("60", "61", "62", "63", "64")):
        out.append("Financial company: debt, ROIC and margin comparisons here are not "
                   "meaningful in the usual way.")
    return out


def history_chart(ticker: str, table: pd.DataFrame, path) -> None:
    years = table.index.astype(int)
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6), dpi=150)
    fig.patch.set_facecolor("white")

    panels = [
        ("Revenue", table["revenue"], "bar"),
        ("Operating margin", table.get("operating_margin"), "line"),
        ("Return on equity", table.get("return_on_equity"), "line"),
    ]
    for ax, (title, series, kind) in zip(axes, panels):
        ax.set_facecolor("white")
        if series is None or series.dropna().empty:
            ax.text(0.5, 0.5, "no data", ha="center", va="center", color=MUTED,
                    transform=ax.transAxes)
        elif kind == "bar":
            ax.bar(years, series.values / 1e9, color=BAR, zorder=3)
            ax.set_ylabel("$ billions", color=MUTED, fontsize=8)
        else:
            ax.plot(years, series.values * 100, color=LINE, linewidth=2, zorder=3)
            ax.set_ylabel("percent", color=MUTED, fontsize=8)
            ax.axhline(0, color=GRID, linewidth=1)
        ax.set_title(title, loc="left", fontsize=10, color=INK, fontweight="bold")
        ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(GRID)
        ax.tick_params(colors=MUTED, labelsize=8)
    suffix = " - DEMO DATA, NOT REAL" if is_demo() else ""
    fig.suptitle(f"{ticker}: ten-year history{suffix}", x=0.01, ha="left", fontsize=12,
                 fontweight="bold", color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(path)
    plt.close(fig)


def main() -> None:
    demo_banner()
    if not INDEX_PATH.exists():
        fail("Nothing fetched yet. Run:  python 01_fetch_company.py TICKER")
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    ticker = index["subject"]
    meta = index["companies"][ticker]
    path = OUTPUT / f"{ticker}_fundamentals.csv"
    if not path.exists():
        fail("No metrics yet. Run:  python 02_metrics.py")
    table = pd.read_csv(path, index_col="fiscal_year")
    latest = table.iloc[-1]
    year = int(table.index[-1])
    price = meta.get("price")

    shares = latest.get("diluted_shares")
    market_cap = price * shares if (price and pd.notna(shares)) else float("nan")
    eps = latest.get("eps_diluted")
    dps = latest.get("dividends_per_share")
    pe = safe_divide(price, eps) if price else float("nan")
    book_per_share = safe_divide(latest.get("equity"), shares)
    pb = safe_divide(price, book_per_share) if price else float("nan")
    dividend_yield = safe_divide(dps, price) if price else float("nan")

    revenue = table["revenue"].dropna()
    span = min(10, len(revenue)) - 1
    growth = cagr(revenue.iloc[-span - 1], revenue.iloc[-1], span) if span > 0 else float("nan")

    size = classify_size(market_cap)
    style = classify_style(growth, dividend_yield,
                           setting_float("GROWTH_THRESHOLD", 0.10),
                           setting_float("YIELD_THRESHOLD", 0.03))
    notes = flags(table, price, meta)
    filing = meta.get("latest_10k") or {}
    demo_warning = ("> **DEMO DATA.** This company does not exist and every number "
                    "below is invented.\n\n") if is_demo() else ""

    def row(label, value):
        return f"| {label} | {value} |"

    lines = [
        f"# {meta['name']} ({ticker})",
        "",
        demo_warning + f"*{meta.get('sic_description') or 'Sector not stated'} · "
        f"{meta.get('exchange') or 'exchange unknown'} · fiscal year {year}*",
        "",
        "## Snapshot",
        "",
        "| | |",
        "|---|---|",
        row("Price", f"{money(price)} ({meta.get('price_source')})" if price else "not available"),
        row("Market cap", money(market_cap)),
        row("Size", size),
        row("Style", style),
        row("Revenue (FY)", money(latest.get("revenue"))),
        row(f"Revenue growth ({span}-year annual)", percent(growth)),
        "",
        "## Is it a good business?",
        "",
        "| Measure | Latest | 5-year average | What it tells you |",
        "|---|---|---|---|",
    ]

    quality = [
        ("Gross margin", "gross_margin", percent,
         "Pricing power. Stable or rising is the trace of a real advantage."),
        ("Operating margin", "operating_margin", percent,
         "Profit from the core business, before financing and tax."),
        ("Net margin", "net_margin", percent, "What finally reaches shareholders."),
        ("Return on equity", "return_on_equity", percent,
         "Profit per dollar of shareholder capital. Flattered by leverage."),
        ("Return on invested capital", "return_on_invested_capital", percent,
         "Profit per dollar of all capital. Harder to flatter."),
        ("Free cash flow margin", "fcf_margin", percent,
         "Cash left after keeping the business running."),
        ("Cash conversion", "cash_conversion", lambda v: ratio(v, 2),
         "Operating cash flow over net income. Below 1.0 for years deserves a look."),
    ]
    for label, column, formatter, meaning in quality:
        series = table[column].dropna() if column in table else pd.Series(dtype=float)
        current = formatter(latest.get(column)) if column in table else "n/a"
        average = formatter(series.tail(5).mean()) if not series.empty else "n/a"
        lines.append(f"| {label} | {current} | {average} | {meaning} |")

    lines += [
        "",
        "## Can it survive a bad year?",
        "",
        "| | |",
        "|---|---|",
        row("Total debt", money(latest.get("total_debt"))),
        row("Cash", money(latest.get("cash"))),
        row("Net debt", money(latest.get("net_debt"))),
        row("Debt to equity", ratio(latest.get("debt_to_equity"), 2)),
        row("Free cash flow", money(latest.get("free_cash_flow"))),
        "",
        "## What do I pay, and what do I get back?",
        "",
        "| | |",
        "|---|---|",
        row("Price to earnings", ratio(pe, 1)),
        row("Price to book", ratio(pb, 1)),
        row("Earnings per share", f"${eps:,.2f}" if pd.notna(eps) else "n/a"),
        row("Dividend per share", f"${dps:,.2f}" if pd.notna(dps) else "none reported"),
        row("Dividend yield", percent(dividend_yield)),
        row("Payout ratio", percent(latest.get("payout_ratio"))),
        row("Diluted shares", f"{shares:,.0f}" if pd.notna(shares) else "n/a"),
        "",
        "A low P/E is not automatically cheap and a high one is not automatically "
        "expensive: both depend on what happens next, which is the part no ratio "
        "knows.",
        "",
    ]

    if notes:
        lines += ["## Worth a second look", ""]
        lines += [f"- {n}" for n in notes]
        lines += [""]
    else:
        lines += ["## Worth a second look", "",
                  "Nothing tripped the automated checks. That is not the same as "
                  "nothing being wrong.", ""]

    lines += [
        "## What this tool cannot tell you",
        "",
        "These decide the investment, and none of them is in a spreadsheet. Read the "
        "annual report and answer them yourself.",
        "",
        "| Question | Where to look in the 10-K |",
        "|---|---|",
        "| What does the company actually sell? | Item 1, Business |",
        "| Which part of the business earns the most? | Item 1, and the segment note |",
        "| Who are the competitors, and what stops them? | Item 1, Competition |",
        "| What could go badly wrong? | Item 1A, Risk Factors |",
        "| What does management say about the year? | Item 7, MD&A |",
        "| Is management any good? | Item 7 over several years: did what they said "
        "would happen, happen? |",
        "| Does it fit my values? | Nothing in the filing answers this. |",
        "",
    ]
    if filing:
        lines += [f"Latest 10-K, filed {filing.get('filed')}: {filing.get('url')}", ""]
    lines += [f"All filings: {meta.get('filings_url')}", "",
              "---", "",
              "*Built from SEC EDGAR XBRL data. Figures are as filed and as later "
              "restated; no adjustment is made for one-off items. This is a research "
              "aid, not investment advice.*", ""]

    out_path = OUTPUT / f"{ticker}_tearsheet.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    history_chart(ticker, table, OUTPUT / f"{ticker}_history.png")

    info(f"Wrote {out_path.name} and {ticker}_history.png")
    print(f"\n{ticker}: {size}, {style}. "
          f"P/E {ratio(pe, 1)}, ROE {percent(latest.get('return_on_equity'))}, "
          f"debt/equity {ratio(latest.get('debt_to_equity'), 2)}")
    if notes:
        print(f"{len(notes)} item(s) flagged for a second look.")
    print("\nCHECKPOINT: open the tear sheet, then open the 10-K link at the bottom "
          "and read Item 1A. The tool has done its half.")
    print("For a peer comparison, run:  python 04_comps.py")


if __name__ == "__main__":
    main()
