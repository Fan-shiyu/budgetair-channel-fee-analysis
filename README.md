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
- `core.py` — the streamlit-free shared core: fee constants, cached loaders, headline
  metrics, `verify_numbers()`, formatters, the Plotly template, and the chart builders.
  Both the dashboard and the MCP server import from here (one source of truth).
- `utils.py` — thin Streamlit layer over `core.py` (page furniture, KPI cards, `chart`).
- `app.py` + `pages/1..5` — Home / The Fee Change / Overall Impact / Winners & Losers /
  What Happened / Direct Opportunity.
- `qa_dashboard.py` — Playwright browser QA (screenshots land in `qa_screenshots/`).

**Deploying on Streamlit Community Cloud:** main file is `app.py`; the committed
`data/outputs/app_data/` files mean the deployed app never needs the 30MB order file.

## MCP server (Phase 4)
An [MCP](https://modelcontextprotocol.io) server so non-technical stakeholders can ask
questions about the fee change **in Claude (or Gemini)** and get correct numbers, charts,
and plain-English explanations. The server owns the facts — nine tools, each answering one
category of question with deterministic Python — and the model only picks a tool and
narrates. Every figure is recomputed from the data; nothing is hardcoded. On startup the
server runs `verify_numbers()` and **refuses to boot** if the data has drifted from the
validated headline figures.

**The nine tools:** `get_overview`, `get_fee_impact(period)`, `fee_for_ticket(price)`,
`winners_losers(dimension)`, `channel_trends`, `direct_opportunity(orders?)`,
`segment_detail(...)`, `get_methodology`, `get_data_catalog`. Every tool returns the same
envelope (headline / data table / plain-English facts / caveats / meta) and, where useful, a
chart PNG rendered with the same styling as the dashboard.

### Run it locally
```
pip install -r requirements.txt
python prepare_app_data.py     # builds data/outputs/app_data/*  (if not already present)
python prepare_mcp_data.py     # builds data/outputs/mcp_data/segments.parquet (~3.6MB)

python -m mcp_server.server --transport http --port 8000     # remote-style (HTTP)
# or
python -m mcp_server.server --transport stdio                # Claude Desktop style
```

### Test it (three layers)
```
pytest tests/                          # Layer 1 (startup gate) + Layer 2 (unit) — 34 tests
# Layer 3 — golden-question eval driven by Gemini (needs a running server + a key):
export GEMINI_API_KEY=...              # or put GEMINI_API_KEY=... in a local .env (gitignored)
python -m mcp_server.server --transport http --port 8000 &   # in one terminal
python eval/golden_eval.py                                   # writes eval/scorecard.md
```
The eval asks the 12 golden questions through the live tools and **hard-fails on any
fabricated $/% figure**. Pass bar: 0 fabrications and ≥10/12 correct. See
`eval/scorecard.md` for the latest run and `eval/manual_claude_checklist.md` for the manual
Claude pass.

### Connect it to Claude

**A. claude.ai custom connector (remote, recommended).** Deploy the server (below) to get a
public HTTPS URL, then in claude.ai: **Settings → Connectors → Add custom connector**, paste
the URL ending in `/mcp`, and enable it. Ask "what did the Aeroprice fee change cost us?" —
Claude will call the tools.

**B. Claude Desktop (local, stdio).** Add this to `claude_desktop_config.json`
(Settings → Developer → Edit Config), then restart Claude Desktop:
```json
{
  "mcpServers": {
    "budgetair": {
      "command": "python",
      "args": ["-m", "mcp_server.server", "--transport", "stdio"],
      "cwd": "C:/Users/you/path/to/budgetair-channel-fee-analysis"
    }
  }
}
```

### Deploy (Google Cloud Run — no cold start)
The `Dockerfile` bakes in the small data files and installs chromium (kaleido needs it for
PNGs). From the repo root, with the [gcloud CLI](https://cloud.google.com/sdk) installed and
a project selected:
```
gcloud run deploy budgetair-mcp \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --min-instances 1 \          # keeps one warm instance -> no 30-60s cold start
  --port 8080
```
Cloud Run prints a public HTTPS URL; the MCP endpoint is that URL + `/mcp`. Re-run the eval
against it: `python eval/golden_eval.py --url https://<your-url>/mcp`, then do the manual
Claude checklist.

> Security note: this demo is **public and read-only on fictional case data**. A production
> deployment would sit behind OAuth with per-user scopes.

### Roadmap — v2 interactive widgets
A future v2 adds MCP-Apps UI resources (a draggable fee-curve explorer and click-to-drill
winners bars) rendered client-side. It is purely additive: every v1 tool already returns a
static chart PNG, so unsupported clients keep working and the golden eval is unaffected.

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
