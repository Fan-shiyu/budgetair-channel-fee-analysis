# BudgetAir Channel Fee Analysis

Solution to the Travix Pricing Analyst business case: impact analysis of the
2022-10-01 Aeroprice channel fee change on BudgetAir.us orders.

## Quick start
```
pip install -r requirements.txt
python prepare_app_data.py  # reads the big order file once -> small chart-ready CSVs
streamlit run app.py        # interactive dashboard
```
The deliverable CSVs already exist in `data/outputs/`. `python analysis.py` rebuilds
them from the raw monthly files and prints a validation block.

## Dashboard (Phase 3)
A 6-page Streamlit dashboard for non-technical business managers — every chart title
is a plain-English finding with the dollar impact, and every number is recomputed from
the data at runtime (nothing hardcoded). A small `verify_numbers()` self-check shows a
warning banner on every page if the data ever drifts from the validated case figures.

- `prepare_app_data.py` — run once; turns `data/outputs/orders_compiled_enriched.csv`
  (30MB) into small files in `data/outputs/app_data/`. The app never reads the big file.
- `utils.py` — cached loaders, fee-scheme constants, `verify_numbers()`, formatters.
- `app.py` + `pages/1..5` — Home / The Fee Change / Overall Impact / Winners & Losers /
  What Happened / Direct Opportunity.
- `qa_dashboard.py` — Playwright browser QA (screenshots land in `qa_screenshots/`).

**Deploying on Streamlit Community Cloud:** main file is `app.py`; the committed
`data/outputs/app_data/` files mean the deployed app never needs the 30MB order file.

## Deliverables
- `outputs/orders_compiled_enriched.csv` — order-level fact table (compiling process, auditable)
- `outputs/impact_summary.csv` — month x channel x zone rollup (analysis-ready)
- `analysis.py` — reproducible pipeline (plain-text readable)
- Slides (PDF) — in outputs/ once final
- Bonus: deployed Streamlit dashboard + MCP server for AI-powered Q&A

## Method in one paragraph
The fee impact is measured by applying both fee schemes to the SAME orders
(counterfactual), which isolates the contract effect from seasonality and mix
shifts. Behavioral effects are measured against Google Flights as a control
channel that had no fee change. See CLAUDE.md for assumptions and validated numbers.
