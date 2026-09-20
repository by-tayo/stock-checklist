"""Tests for the metric math and XBRL parsing in sc_common.py.

Run:  python -m pytest -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sc_common import (annual_flow, annual_instant, cagr, classify_size,  # noqa: E402
                       classify_style, derive_metrics, money, percent, ratio,
                       safe_divide)


def facts(tag: str, rows: list[dict], unit: str = "USD") -> dict:
    return {"facts": {"us-gaap": {tag: {"units": {unit: rows}}}}}


def year_row(fy: int, val: float, form="10-K", accn="a", start=None, end=None) -> dict:
    return {"start": start or f"{fy}-01-01", "end": end or f"{fy}-12-31",
            "fy": fy, "fp": "FY", "form": form, "val": val, "accn": accn}


# ---------------------------------------------------------------- XBRL parsing

def test_annual_flow_keeps_full_year_periods_only():
    rows = [year_row(2023, 1000),
            {"start": "2023-01-01", "end": "2023-03-31", "fy": 2023, "fp": "Q1",
             "form": "10-K", "val": 250, "accn": "a"}]
    result = annual_flow(facts("Revenues", rows), ["Revenues"])
    assert result.loc[2023] == 1000


def test_annual_flow_ignores_quarterly_filings():
    rows = [year_row(2023, 1000), year_row(2023, 999, form="10-Q", accn="b")]
    result = annual_flow(facts("Revenues", rows), ["Revenues"])
    assert result.loc[2023] == 1000


def test_annual_flow_prefers_the_latest_restatement():
    rows = [year_row(2022, 500, accn="0001"), year_row(2022, 520, accn="0002")]
    result = annual_flow(facts("Revenues", rows), ["Revenues"])
    assert result.loc[2022] == 520


def test_annual_flow_falls_back_through_tag_list():
    rows = [year_row(2023, 700)]
    payload = facts("SalesRevenueNet", rows)
    result = annual_flow(payload, ["Revenues", "SalesRevenueNet"])
    assert result.loc[2023] == 700


def test_annual_flow_returns_empty_when_no_tag_matches():
    result = annual_flow(facts("Revenues", [year_row(2023, 1)]), ["GrossProfit"])
    assert result.empty


def test_annual_flow_merges_years_across_a_tag_switch():
    """A filer that moves a concept to a different tag partway through its history
    (NVIDIA moved revenue back to the legacy `Revenues` tag after FY2022) must not
    lose the years reported only under the other tag."""
    payload = {"facts": {"us-gaap": {
        "RevenueFromContractWithCustomerExcludingAssessedTax":
            {"units": {"USD": [year_row(2021, 100), year_row(2022, 110)]}},
        "Revenues": {"units": {"USD": [year_row(2022, 999), year_row(2023, 120)]}},
    }}}
    result = annual_flow(payload, ["RevenueFromContractWithCustomerExcludingAssessedTax",
                                   "Revenues"])
    assert result.loc[2021] == 100
    assert result.loc[2022] == 110  # preferred tag wins where both report a year
    assert result.loc[2023] == 120  # gap year filled from the fallback tag


def test_annual_instant_skips_rows_with_a_start_date():
    rows = [{"end": "2023-12-31", "fy": 2023, "form": "10-K", "val": 5000, "accn": "a"},
            year_row(2023, 111)]
    result = annual_instant(facts("Assets", rows), ["Assets"])
    assert result.loc[2023] == 5000


def test_annual_flow_handles_52_53_week_fiscal_years():
    """Retailers file 52/53-week years that are not exactly 365 days."""
    rows = [{"start": "2023-01-29", "end": "2024-02-03", "fy": 2023, "fp": "FY",
             "form": "10-K", "val": 900, "accn": "a"}]
    result = annual_flow(facts("Revenues", rows), ["Revenues"])
    assert result.loc[2023] == 900


# ---------------------------------------------------------------- safe math

def test_safe_divide_handles_zero_and_missing():
    assert safe_divide(10, 2) == 5
    assert pd.isna(safe_divide(10, 0))
    assert pd.isna(safe_divide(None, 5))
    assert pd.isna(safe_divide(5, None))
    assert pd.isna(safe_divide(float("nan"), 5))


def test_cagr_basic():
    assert cagr(100, 200, 1) == pytest.approx(1.0)
    assert cagr(100, 121, 2) == pytest.approx(0.10)


def test_cagr_is_undefined_for_negative_or_zero_values():
    assert pd.isna(cagr(-10, 50, 3))
    assert pd.isna(cagr(0, 50, 3))
    assert pd.isna(cagr(10, 20, 0))


# ---------------------------------------------------------------- derived metrics

def sample_table() -> pd.DataFrame:
    return pd.DataFrame({
        "revenue": [1000.0, 1200.0],
        "gross_profit": [400.0, 500.0],
        "operating_income": [200.0, 260.0],
        "net_income": [150.0, 200.0],
        "operating_cash_flow": [180.0, 240.0],
        "capex": [50.0, 60.0],
        "equity": [1000.0, 1100.0],
        "cash": [100.0, 150.0],
        "long_term_debt": [400.0, 380.0],
        "short_term_debt": [100.0, 120.0],
        "eps_diluted": [1.50, 2.00],
        "dividends_per_share": [0.50, 0.60],
    }, index=[2022, 2023])


def test_derived_margins_and_returns():
    out = derive_metrics(sample_table())
    row = out.loc[2023]
    assert row["gross_margin"] == pytest.approx(500 / 1200)
    assert row["operating_margin"] == pytest.approx(260 / 1200)
    assert row["net_margin"] == pytest.approx(200 / 1200)
    assert row["return_on_equity"] == pytest.approx(200 / 1100)
    assert row["free_cash_flow"] == pytest.approx(240 - 60)
    assert row["revenue_growth"] == pytest.approx(0.2)
    assert row["payout_ratio"] == pytest.approx(0.6 / 2.0)
    assert row["cash_conversion"] == pytest.approx(240 / 200)


def test_total_and_net_debt():
    out = derive_metrics(sample_table())
    assert out.loc[2023, "total_debt"] == pytest.approx(500)
    assert out.loc[2023, "net_debt"] == pytest.approx(350)
    assert out.loc[2023, "debt_to_equity"] == pytest.approx(500 / 1100)


def test_return_on_invested_capital_uses_equity_plus_debt():
    out = derive_metrics(sample_table())
    assert out.loc[2023, "return_on_invested_capital"] == pytest.approx(260 / 1600)


def test_zero_equity_gives_nan_not_infinity():
    table = sample_table()
    table.loc[2023, "equity"] = 0.0
    out = derive_metrics(table)
    assert pd.isna(out.loc[2023, "return_on_equity"])
    assert pd.isna(out.loc[2023, "debt_to_equity"])


def test_missing_gross_profit_does_not_break_the_table():
    table = sample_table().drop(columns=["gross_profit"])
    out = derive_metrics(table)
    assert "operating_margin" in out
    assert out.loc[2023, "operating_margin"] == pytest.approx(260 / 1200)


# ---------------------------------------------------------------- classification

def test_size_buckets():
    assert classify_size(500e9) == "mega cap"
    assert classify_size(50e9) == "large cap"
    assert classify_size(5e9) == "mid cap"
    assert classify_size(1e9) == "small cap"
    assert classify_size(100e6) == "micro cap"
    assert classify_size(float("nan")) == "unknown"


def test_style_labels():
    assert classify_style(0.20, 0.001) == "growth"
    assert classify_style(0.02, 0.04) == "income"
    assert classify_style(0.20, 0.04) == "growth with income"
    assert classify_style(0.02, 0.001) == "neither clearly growth nor income"


def test_style_handles_missing_inputs():
    assert classify_style(float("nan"), float("nan")) == "neither clearly growth nor income"


# ---------------------------------------------------------------- formatting

def test_money_scales_and_handles_missing():
    assert money(1_500_000_000) == "$1.50B"
    assert money(2_500_000) == "$2.50M"
    assert money(float("nan")) == "n/a"


def test_percent_and_ratio_handle_missing():
    assert percent(0.1234) == "12.3%"
    assert percent(None) == "n/a"
    assert ratio(1.234, 2) == "1.23"
    assert ratio(float("nan")) == "n/a"
