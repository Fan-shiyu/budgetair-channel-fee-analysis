# BudgetAir Channel Fee Analysis — Project Spec

## What this project is
Solution to the Travix Pricing Analyst business case (BudgetAir.us, 2022 orders).
The Aeroprice partner channel fee changed on 2022-10-01. We quantify the impact,
identify winners/losers, and recommend pricing + Direct-channel strategy.

**Audience rule (applies to EVERYTHING built here): business managers with NO
technical background. Every chart needs a plain-English takeaway title stating
the commercial impact in $, not a metric name. Say "This change would have cost
us $132k on last year's orders", never "fee_delta aggregated by zone". No
jargon: not "counterfactual" -> "same orders, both price schemes"; not
"DiD" -> "compared against a channel that had no fee change".**

## Locked assumptions — never change without user approval
- Total Ticket Value = Base Fare + Tax
- Fee applied PER ORDER (per-passenger = appendix sensitivity only)
- OLD fee (before 2022-10-01): min(4.0% x Ticket, $24.00), min $0
- NEW fee (from 2022-10-01): clip(3.8% x Ticket, $10.50, $19.00)
- 362 zero-ticket orders flagged `is_zero_ticket`, excluded from fee math
- Margin is net of all costs incl. actual fee -> impact = counterfactual
  (both schemes applied to the SAME orders; immune to seasonality)
- Fee columns exist ONLY for Aeroprice (other channels' terms unknown)
- Break-evens: new fee > old below $262.50 ticket; new cap binds from $500

## Validated headline numbers — the single source of truth
Slides, dashboard and MCP answers MUST reproduce these exactly (from analysis.py):

| Metric | Value |
|---|---|
| Full-year counterfactual delta (new - old, all 2022 Aeroprice orders) | **+$131,696 more expensive** |
| Oct-Dec actual orders (n=12,220) | old $184,077 / new $182,309 = **-$1,768 (-1.0%)** |
| Jan-Sep orders (n=46,799) | **+$133,464 (+27.9%)** = 59% of Jan-Sep Aeroprice margin |
| Floor zone <$262.50: 34,554 orders (59% of channel) | avg **+$6.41**/order, total +$221k, avg margin -$0.67 |
| Cap zone >$500: 17,702 orders (30%) | avg **-$4.79**/order, total -$85k |
| Tickets <$100 (33.8% of Aeroprice) | effective fee rate 4.0% -> **17.6%**; +$8.09/order vs -$3.19 avg margin |
| Losers (avg fee delta) | Avianca +$6.64, Spirit +$6.46, Frontier +$5.87, LATAM +$5.05; one-way +$3.89; domestic +$5.76 |
| Winners | Turkish -$2.66, Aer Lingus -$2.48; intl returns -$3.73 |
| Behavior: cheap-fare (<$262.50) monthly volume Jul-Sep -> Oct-Dec | Aeroprice **-58.5%** vs Google Flights (control, no fee change) **-5.1%** -> ~-53pp attributable |
| Aeroprice share of all cheap-fare orders | ~75% pre -> ~50% post |
| Direct share of cheap fares vs trend projection | Nov 9.47% vs 9.38 proj; Dec **11.38% vs 9.78 proj** (small, late, positive spillover) |
| Total cheap-fare orders all channels | ~5,600/mo -> ~3,100/mo: most displaced demand NOT recaptured |
| Sensitivity: per-passenger fee basis, full-year delta | +$231,170 (worse than per-order) |

## The narrative (one storyline connecting all four case questions)
1. The new contract looks cheaper (lower %, lower cap) but the new $10.50
   floor hit 59% of the channel's orders — segments already at ~zero margin.
2. On today's (post-change) sales mix the contract is cost-neutral; on the mix
   we actually had, it costs +$132k/yr. It is only "neutral" because the
   punished segment already left the channel.
3. Cheap fares collapsed in Aeroprice (-58.5% vs -5.1% control). Most of that
   demand was NOT recaptured by our other channels -> likely lost to competitors.
4. Strategy: (a) stop full-price competition on sub-$262 fares in Aeroprice
   (structurally unprofitable there), (b) reinvest the $5/order cap saving
   into sharper prices on >$500 fares, (c) make Direct the designated home
   for budget fares — every captured order saves >=$10.50 in fees, (d) use
   the +$132k full-year number to renegotiate a tiered fee.

## Repo layout
```
data/                     # 12 raw monthly CSVs (do not modify)
analysis.py               # reproducible pipeline -> writes outputs/
outputs/
  orders_compiled_enriched.csv   # deliverable CSV 1 (order-level fact table)
  impact_summary.csv             # deliverable CSV 2 (month x channel x zone)
app.py                    # Streamlit dashboard (TO BUILD)
mcp_server/               # FastMCP server (TO BUILD)
CLAUDE.md                 # this file
requirements.txt
```
Reproducibility: run `python analysis.py`; console prints validation block that
must match the table above. Compare output md5sums across environments.

## Dashboard spec (app.py — Streamlit, TO BUILD)
- Reads ONLY outputs/*.csv (never recompute fees; no heavy work in app)
- Plotly charts (built-in PNG export — user screenshots them into slides)
- Sidebar: month range + channel filters. Big KPI cards, plain language.
- 5 pages mirroring the slide storyline:
  1. **The Change** — old vs new fee curve by ticket value (one line chart,
     shaded "pays more"/"pays less" regions, break-even at $262.50 marked)
  2. **Overall Impact** — KPI cards (+$132k full-year, -$1.8k Q4-only, 59% of
     margin); monthly delta bar chart; the two-mixes explanation in one sentence
  3. **Winners & Losers** — zone table + carrier bar chart (red/green),
     the "$100 ticket now pays 17.6% fee" callout
  4. **What Happened** — cheap-fare volume lines: Aeroprice vs Google Flights
     (control) with Oct-1 vertical marker; Aeroprice median ticket jump
  5. **Direct Opportunity** — Direct cheap-fare share vs trend; "$10.50 saved
     per captured order" calculator (slider: orders shifted -> $ saved/yr)
- Every page: one bolded takeaway sentence at top, commercial impact in $.

## MCP server spec (mcp_server/ — FastMCP, TO BUILD)
- Reads the two output CSVs (summary first; order-level only for drill-down)
- Curated tools only (no raw SQL): get_kpis(period, channel),
  compare_fee_schemes(segment), winners_losers(dimension), channel_mix_trend()
- Tool docstrings written for business users; returns include a one-line
  plain-English interpretation alongside numbers
- Primary: remote HTTP deployment (Claude.ai custom connector);
  backup: local stdio config for Claude Desktop
- Numbers returned must tie out to the validated table above

## Style guide for slides & dashboard
- Titles are findings, not topics ("The new floor made 1 in 3 orders
  unprofitable to sell", not "Fee Analysis")
- Red = pays more / loses; green = pays less / wins; grey = neutral
- Round to whole $ or 1 decimal %; never show raw floats
- Always pair a % with the $ amount it represents
