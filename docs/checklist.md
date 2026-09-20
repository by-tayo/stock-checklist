# The investment checklist

Every question a beginner's checklist asks, and where the answer comes from. The split
matters: about half can be computed, and the half that decides the investment cannot.

## What the company is

| Question | Answered by |
|---|---|
| What products and services does it sell? | **You.** 10-K Item 1, Business |
| Which part of the business earns the most? | **You.** Item 1 and the segment note (see limitation 3 in methodology) |
| Is it more or less diversified than competitors? | **You**, comparing segment notes across the peers in your comps run |
| Which industry, and which exchange? | Tool — SIC description and exchange, from the SEC submissions data |
| How big is it? | Tool — market cap and size bucket |

## Is it a good business?

| Question | Answered by |
|---|---|
| Does it have a competitive advantage? | Tool gives the trace: gross margin level and trend, and return on invested capital. **You** decide what causes it and whether it lasts |
| Is the business model sound? | **You.** Item 1 and Item 7 |
| Is management any good? | **You.** Read Item 7 across several years: did what they said would happen, happen? Capital allocation shows up in ROIC, buybacks and debt |
| Does it have significant market share? | **You.** Not in filings; approximate it as revenue against peer revenue in `comps.csv` |
| Are there new developments? | **You.** Item 1, Item 7, and recent 8-K filings |

## Can it survive a bad year?

| Question | Answered by |
|---|---|
| How much debt? | Tool — total debt, net debt, debt to equity |
| Does it generate cash? | Tool — operating cash flow, free cash flow, FCF margin |
| Are the earnings real? | Tool — cash conversion, operating cash flow against net income |
| What could go wrong? | **You.** Item 1A, Risk Factors |

## What do I pay, and what do I get back?

| Question | Answered by |
|---|---|
| What is the market cap? | Tool — price × diluted shares |
| How expensive is it? | Tool — P/E and P/B, against peers in the comps table |
| Does it pay a dividend, and is it safe? | Tool — dividend per share, yield, payout ratio |
| Total return? | Price change plus dividends. Needs price history; not in this tool yet |
| Growth stock, income stock, or neither? | Tool labels it from growth rate and yield. A label, not a verdict |

## Flags the tool raises

Not verdicts — reasons to look closer:

- Trades under $5, or not listed on a major exchange (penny stock and pink-sheet
  territory, where disclosure is thin)
- Lost money last year
- Revenue fell in three of the last five years
- Debt more than twice equity, or negative book equity
- Cash flow persistently below reported earnings
- Dividends larger than earnings
- Share count up more than 10% in five years (dilution)
- Financial company, where these ratios don't mean what they usually mean

## After you own it

The book's point, and the tool's limit. Once you hold shares, what you monitor is
press releases, each new quarterly filing, and the price relative to what you thought
the business was worth. Re-running this tool after each annual report tells you
whether the numbers still say what they said when you bought.

## What no checklist covers

Whether the company fits your values, whether you understand it well enough to hold
it through a bad year, and whether the money is money you can afford to leave alone.
Those are yours.
