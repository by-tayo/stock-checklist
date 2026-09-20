# Methodology

Where every number comes from, and what it can't tell you.

## Data sources

| What | Source | Key needed |
|---|---|---|
| Company financials | SEC EDGAR XBRL company facts API | No key, but a `User-Agent` naming you and a contact email is required |
| Company profile, filings list | SEC EDGAR submissions API | Same |
| Share price | Alpha Vantage `GLOBAL_QUOTE`, or typed into `data/prices_manual.csv` | Free key, 25 requests/day |

The SEC asks for no more than 10 requests per second; this tool pauses between calls
and caches every company's facts to `data/cache/`, so re-runs hit the network only for
prices.

## Reading XBRL

Each figure is looked up through a list of tags in preference order, because filers
tag the same idea differently. Revenue alone appears as
`RevenueFromContractWithCustomerExcludingAssessedTax`, `Revenues`, `SalesRevenueNet`
and others. If none match, the field is blank rather than guessed.

**Adding a tag:** find the concept name in the company's filing on EDGAR, add it to
the relevant list in `FLOW_TAGS` or `INSTANT_TAGS` in `sc_common.py`, and re-run.

Two rules govern which rows count:

- **Annual only.** Rows must come from a 10-K and cover 330 to 400 days. The window is
  wide because retailers file 52- and 53-week fiscal years that are not 365 days.
- **Latest statement wins.** When a company restates a prior year, the same fiscal year
  appears more than once with different values. The most recently filed figure is used.

Balance-sheet items are point-in-time: rows with a start date are ignored, since those
are period flows rather than balances.

## The ratios

| Ratio | Formula | Notes |
|---|---|---|
| Gross / operating / net margin | each profit line ÷ revenue | |
| Free cash flow | operating cash flow − capital expenditure | The usual simple definition |
| Return on equity | net income ÷ shareholders' equity | Rises with leverage, so read it beside debt |
| Return on invested capital | operating income ÷ (equity + total debt) | A simplification: no tax adjustment, no excess-cash deduction |
| Debt to equity | (long-term + short-term debt) ÷ equity | |
| Cash conversion | operating cash flow ÷ net income | Below 1.0 for years is an earnings-quality question |
| Payout ratio | dividends per share ÷ diluted EPS | Above 1.0 means the dividend is not covered by profit |
| P/E, P/B | price ÷ EPS, price ÷ book value per share | Needs a price; blank without one |
| Market cap | price × diluted shares | Diluted, so it is slightly conservative |

Division by zero or a missing input returns blank, never infinity.

## Classification thresholds

These are **market conventions, not rules**, and they move around:

- Mega cap $200B+, large cap $10B+, mid cap $2B+, small cap $300M+, micro cap below
- "Growth" if revenue has compounded at 10%+, "income" if the dividend yields 3%+

Both growth and yield thresholds are editable in `.env`. They produce a label, not a
judgment.

## Limitations

1. **As-filed figures, unadjusted.** A year with a big one-off gain, an impairment or
   a legal settlement will look better or worse than the underlying business. Analysts
   adjust for these by hand after reading the filing. This tool does not.
2. **Financial companies don't fit.** For banks and insurers, debt is raw material
   rather than a burden, and margin and ROIC comparisons mislead. The tool flags them
   by SIC code and you should treat the ratios as meaningless there.
3. **No segment breakdown yet.** "Which part of the business earns the most" is
   reported inconsistently in XBRL segment tags, and parsing it badly is worse than
   not parsing it. The tear sheet links to the segment note instead.
4. **US filers only.** Foreign companies file 20-F or 40-F and won't appear in the
   ticker list. Neither will most OTC and pink-sheet companies, which often file very
   little at all — and that opacity is itself the finding.
5. **The price is a snapshot.** Ratios that use it are only as current as the last
   price fetch, cached per day.
6. **Everything here is backward-looking.** The ratios describe what a company has
   already done. What you pay for is what it does next.
7. **Peers are chosen by you.** The tool does not verify that they are comparable,
   and a comparison against the wrong peers is worse than no comparison. It warns when
   the SIC industries differ, which catches only the obvious cases.

## What this is not

Not investment advice, and not a screener that ranks or scores companies. It computes
the measurable half of an investment checklist so that your attention goes to the half
that requires reading and judgment.
