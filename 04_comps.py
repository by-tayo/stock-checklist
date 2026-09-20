"""Step 4: compare the subject with its peers.

Run:  python 04_comps.py

Writes output/comps.csv and output/comps.png. Needs at least one peer:
  python 01_fetch_company.py AAPL MSFT GOOGL
"""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from sc_common import (CACHE, OUTPUT, cagr, demo_banner, fail, info, is_demo, money,
                       percent, ratio, safe_divide, warn)

INDEX_PATH = CACHE / "company_index.json"
SUBJECT_COLOR = "#2a78d6"
PEER_COLOR = "#b9c6d4"
INK = "#1f1f1e"
MUTED = "#6b6a63"
GRID = "#e4e3dc"


def summarize(ticker: str, meta: dict) -> dict:
    path = OUTPUT / f"{ticker}_fundamentals.csv"
    if not path.exists():
        fail(f"No metrics for {ticker}. Run:  python 02_metrics.py")
    table = pd.read_csv(path, index_col="fiscal_year")
    latest = table.iloc[-1]
    price = meta.get("price")
    shares = latest.get("diluted_shares")
    revenue = table["revenue"].dropna()
    span = min(5, len(revenue)) - 1
    growth = cagr(revenue.iloc[-span - 1], revenue.iloc[-1], span) if span > 0 else float("nan")
    market_cap = price * shares if (price and pd.notna(shares)) else float("nan")
    return {
        "ticker": ticker,
        "name": meta.get("name", ""),
        "fiscal_year": int(table.index[-1]),
        "market_cap": market_cap,
        "revenue": latest.get("revenue"),
        "revenue_cagr_5y": growth,
        "gross_margin": latest.get("gross_margin"),
        "operating_margin": latest.get("operating_margin"),
        "net_margin": latest.get("net_margin"),
        "return_on_equity": latest.get("return_on_equity"),
        "debt_to_equity": latest.get("debt_to_equity"),
        "fcf_margin": latest.get("fcf_margin"),
        "pe": safe_divide(price, latest.get("eps_diluted")) if price else float("nan"),
        "dividend_yield": (safe_divide(latest.get("dividends_per_share"), price)
                           if price else float("nan")),
    }


def chart(frame: pd.DataFrame, subject: str, path) -> None:
    panels = [("Operating margin", "operating_margin", 100),
              ("Return on equity", "return_on_equity", 100),
              ("Revenue growth, 5-year annual", "revenue_cagr_5y", 100),
              ("Price to earnings", "pe", 1)]
    fig, axes = plt.subplots(1, len(panels), figsize=(13, 3.8), dpi=150)
    fig.patch.set_facecolor("white")
    for ax, (title, column, scale) in zip(axes, panels):
        data = frame[["ticker", column]].dropna()
        ax.set_facecolor("white")
        if data.empty:
            ax.text(0.5, 0.5, "no data", ha="center", va="center", color=MUTED,
                    transform=ax.transAxes)
        else:
            colors = [SUBJECT_COLOR if t == subject else PEER_COLOR
                      for t in data["ticker"]]
            ax.bar(data["ticker"], data[column] * scale, color=colors, zorder=3)
            if scale == 100:
                ax.set_ylabel("percent", color=MUTED, fontsize=8)
        ax.set_title(title, loc="left", fontsize=10, color=INK, fontweight="bold")
        ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(GRID)
        ax.tick_params(colors=MUTED, labelsize=8)
    suffix = " - DEMO DATA, NOT REAL" if is_demo() else ""
    fig.suptitle(f"{subject} (blue) against its peers{suffix}", x=0.01, ha="left",
                 fontsize=12, fontweight="bold", color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(path)
    plt.close(fig)


def main() -> None:
    demo_banner()
    if not INDEX_PATH.exists():
        fail("Nothing fetched yet. Run:  python 01_fetch_company.py TICKER PEER PEER")
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    subject = index["subject"]
    if len(index["companies"]) < 2:
        fail("Only one company fetched. Comparison needs peers, for example:\n"
             f"  python 01_fetch_company.py {subject} PEER1 PEER2")

    rows = [summarize(t, m) for t, m in index["companies"].items()]
    frame = pd.DataFrame(rows)
    numeric = frame.drop(columns=["ticker", "name"]).select_dtypes("number")
    median = numeric.median(numeric_only=True)
    median["ticker"] = "MEDIAN"
    median["name"] = "Peer group median"
    out = pd.concat([frame, pd.DataFrame([median])], ignore_index=True)
    out.to_csv(OUTPUT / "comps.csv", index=False)
    chart(frame, subject, OUTPUT / "comps.png")

    sectors = {m.get("sic_description", "") for m in index["companies"].values()}
    if len(sectors) > 1:
        warn("The companies are in different SIC industries: "
             + "; ".join(s for s in sectors if s)
             + ". A comparison across industries is a weak comparison.")

    print(f"\nPeer comparison, {subject} against {len(frame) - 1} peer(s)\n")
    header = (f"{'Ticker':<8}{'Mkt cap':>11}{'Revenue':>11}{'Op mgn':>9}{'ROE':>9}"
              f"{'Growth':>9}{'D/E':>7}{'P/E':>8}{'Yield':>8}")
    print(header)
    print("-" * len(header))
    for _, r in out.iterrows():
        mark = "*" if r["ticker"] == subject else " "
        print(f"{mark}{str(r['ticker']):<7}{money(r['market_cap']):>11}"
              f"{money(r['revenue']):>11}{percent(r['operating_margin'], 0):>9}"
              f"{percent(r['return_on_equity'], 0):>9}"
              f"{percent(r['revenue_cagr_5y'], 0):>9}"
              f"{ratio(r['debt_to_equity'], 1):>7}{ratio(r['pe'], 1):>8}"
              f"{percent(r['dividend_yield'], 1):>8}")
    print("-" * len(header))
    info("Wrote comps.csv and comps.png")
    print("\nCHECKPOINT: peers must be genuinely comparable - same industry, roughly "
          "comparable size and business model. A cheap-looking P/E against the wrong "
          "peers tells you nothing.")


if __name__ == "__main__":
    main()
