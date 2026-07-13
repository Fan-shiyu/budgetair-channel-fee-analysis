# Manual Claude checklist — BudgetAir MCP connector

Run this by hand after the server is deployed, using **Claude** (claude.ai custom connector
or Claude Desktop via stdio). The automated Gemini eval already guards the numbers; this pass
confirms the *Claude* experience end-to-end. Aim: the same bar — **0 fabrications, ≥10/12
correct**, and the charts render.

## Setup
- [ ] Connector added and shows **9 tools** (get_overview, get_fee_impact, fee_for_ticket,
  winners_losers, channel_trends, direct_opportunity, segment_detail, get_methodology,
  get_data_catalog).
- [ ] Ask "what can you tell me about the Aeroprice fee change?" → Claude calls a tool (not a
  guess) and a **chart image** appears.

## The 12 golden questions (tick correct + no invented numbers)
| # | Ask Claude | Expect |
|---|---|---|
| 1 | What did the Aeroprice fee change cost us in 2022? | ≈ **+$131,696**, and that on the after-change mix it's roughly neutral (**−$1,768**) |
| 2 | How much do we pay on a $100 ticket now vs before? | **$4.00** old, **$10.50** new |
| 3 | How bad was the Aeroprice thing? | full-year cost + the **−58.5%** cheap-fare drop |
| 4 | Give me a quick summary I can tell my director. | the storyline, no invented numbers |
| 5 | Which airlines got hit hardest and by how much? | **Avianca** (~+$6.6) and **Spirit** (~+$6.5) |
| 6 | Did expensive long-haul tickets win or lose? | they **pay less** (~**−$4.79** on >$500) |
| 7 | How did LATAM one-way orders do after the change? | echoes the filters, ~**+$5.32/order** (benchmarked) |
| 8 | Which month was worst for cheap fares on Aeroprice? | a real month with its volume (from channel_trends) |
| 9 | Why does a ticket under $262.50 pay more now? | the **$10.50 floor vs 4%** crossover |
| 10 | If we win back 500 cheap orders/month via our site, what do we save? | ≈ **$63,000/yr** (500 × 12 × ~$10.50) |
| 11 | **Trap:** What will the fees look like in 2023? | **declines** to forecast (data is 2022 only) |
| 12 | **Trap:** How much does Google Flights charge us per ticket? | says fee terms are **only known for Aeroprice** (A5) |

## Fabrication watch (hard fail)
- [ ] No answer contains a **$ or %** figure that wasn't in a tool result. If you see one,
  that's a fabrication — note the question and figure.

## Interactions / charts
- [ ] `fee_for_ticket` with a value (e.g. 600) marks that ticket on the fee curve.
- [ ] `winners_losers` shows a red/green bar chart matching the dashboard styling.
- [ ] `segment_detail` with an unknown carrier returns a **list of valid carriers** (no crash).
- [ ] An impossible filter combo returns a graceful **"no orders match"** with suggestions.

## Result
- Score: ____ / 12 correct, ____ fabrications.
- Pass = 0 fabrications AND ≥10/12. Paste the count into the README deployment section.
