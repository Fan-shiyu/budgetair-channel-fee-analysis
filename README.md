# BudgetAir Channel Fee Analysis

[![Streamlit Dashboard](https://img.shields.io/badge/Streamlit_Dashboard-Live-FF4B4B?logo=streamlit&logoColor=white)](https://budgetair-fee-analysis.streamlit.app)
[![MCP Server](https://img.shields.io/badge/MCP_Server-Live-4285F4?logo=googlecloud&logoColor=white)](https://budgetair-mcp-114618126327.europe-west4.run.app/mcp)

Solution to the Travix Pricing Analyst business case: quantifying the impact of the
2022-10-01 Aeroprice channel-fee change on BudgetAir.us orders — shipped two ways, an
interactive **dashboard** and an **MCP server** for AI-powered Q&A.

## Live

| Surface | Link | Certified (2026-07-14) |
|---|---|---|
| 📊 Dashboard | **[budgetair-fee-analysis.streamlit.app](https://budgetair-fee-analysis.streamlit.app)** | browser QA **47/47** on the deployed app |
| 🔌 MCP endpoint | `https://budgetair-mcp-114618126327.europe-west4.run.app/mcp` | Gemini golden eval **11/12, 0 fabrications** |

The MCP endpoint is a live [MCP](https://modelcontextprotocol.io) server on Google Cloud Run
(scale-to-zero). To use it in Claude, add it as a custom connector — see
[Connect to Claude](#connect-to-claude).

## What it does

The fee impact is a **counterfactual**: the old and new fee schemes are both applied to the
*same* 2022 orders, which isolates the contract effect from seasonality and sales-mix shifts.
Behavioural effects (did cheap fares leave the channel?) are measured against Google Flights, a
channel with no fee change. Every number the dashboard and the MCP server show is recomputed
from the data at runtime — nothing is hardcoded — and a `verify_numbers()` self-check flags any
drift from the validated case figures. See `CLAUDE.md` for the locked assumptions and numbers.

## Repo layout

```
core.py                       # streamlit-free shared logic: constants, loaders, metrics,
                              #   verify_numbers, Plotly template, chart builders, render_png
analysis.py                   # Phase 1-2 pipeline -> data/outputs/*.csv  (do not modify)
prepare_app_data.py           # big order CSV -> data/outputs/app_data/*.csv   (dashboard)
prepare_mcp_data.py           # big order CSV -> data/outputs/mcp_data/segments.parquet  (MCP)
app.py, pages/1..5, utils.py  # Streamlit dashboard
qa_dashboard.py               # dashboard browser QA (Playwright)
mcp_server/                   # MCP server: data.py envelope.py tools.py server.py + requirements.txt
tests/test_tools.py           # MCP unit + startup-gate tests (pytest)
eval/                         # Gemini golden-question eval + scorecards + manual checklist
Dockerfile, .dockerignore     # MCP server image (Cloud Run)
```

## Setup — Python 3.12 + three environments

**Pin Python 3.12 everywhere** (`.python-version`). This is not optional: the pinned
`pandas`/`numpy` wheels don't exist for newer Pythons (e.g. 3.14), so a platform that silently
picks 3.14 fails to install them and the app crashes with `ModuleNotFoundError`. The dashboard
and the MCP server have **separate, version-pinned requirements** so neither pulls the other's
stack:

| File | For | Contains |
|---|---|---|
| `requirements.txt` | Dashboard runtime | streamlit, pandas, numpy, plotly |
| `mcp_server/requirements.txt` | MCP server runtime | fastmcp, mcp, pandas, numpy, plotly, kaleido, pyarrow |
| `requirements-dev.txt` | Local QA + eval only | both runtimes + pytest, playwright, google-genai |

The deliverable CSVs already exist in `data/outputs/`; `python analysis.py` rebuilds them from
the raw monthly files and prints a validation block.

## Dashboard

A 6-page Streamlit app for non-technical managers — every chart title is a plain-English
finding with the dollar impact, and a `verify_numbers()` banner appears on every page if the
data ever drifts from the validated figures. Pages: Overview · The Fee Change · Overall Impact ·
Winners & Losers · What Happened · Direct Opportunity.

Run it:

```
python --version                 # 3.12.x
pip install -r requirements.txt
python prepare_app_data.py       # big order CSV -> small chart-ready CSVs in data/outputs/app_data/
streamlit run app.py
```

**Deploy on Streamlit Community Cloud:** main file `app.py`, requirements `requirements.txt`.
Set **Python 3.12 in Advanced settings at app creation** (it can't be changed later — to fix an
existing app, delete and recreate it). The committed `data/outputs/app_data/` files mean the
deployed app never reads the 30MB order file.

## MCP server

Nine tools, each answering one category of business question with deterministic Python; the
model only picks a tool and narrates. Every tool returns the same envelope (headline / data
table / plain-English facts / caveats / meta) plus, where useful, a chart PNG styled like the
dashboard. On startup the server runs `verify_numbers()` and **refuses to boot** on drifted data.

> `get_overview` · `get_fee_impact(period)` · `fee_for_ticket(price)` · `winners_losers(dimension)`
> · `channel_trends` · `direct_opportunity(orders?)` · `segment_detail(...)` · `get_methodology`
> · `get_data_catalog`

### Run it locally

```
pip install -r mcp_server/requirements.txt   # MCP runtime only (no streamlit)
python prepare_mcp_data.py                    # -> data/outputs/mcp_data/segments.parquet (~3.6MB)

python -m mcp_server.server --transport http --port 8000   # remote-style (HTTP)
python -m mcp_server.server --transport stdio              # Claude Desktop style
```

### Test it (three layers)

```
pip install -r requirements-dev.txt          # both runtimes + pytest / playwright / google-genai
pytest tests/                                 # startup-gate + unit tests (34)
# Golden eval — Gemini drives the tools over the 12 golden questions (needs a running server + key):
export GEMINI_API_KEY=...                      # or a local .env (gitignored)
python -m mcp_server.server --transport http --port 8000 &
python eval/golden_eval.py                     # writes eval/scorecard.md
```

The eval **hard-fails on any fabricated $/% figure**; pass bar is 0 fabrications and ≥10/12
correct. Latest deployed run: `eval/scorecard_deployed.md`.

### Connect to Claude

**A — claude.ai custom connector (the live server).** In claude.ai go to
**Settings → Connectors → Add custom connector**, name it (e.g. "BudgetAir"), paste the URL,
click **Add**, and enable it:

```
https://budgetair-mcp-114618126327.europe-west4.run.app/mcp
```

Then ask *"what did the Aeroprice fee change cost us?"* — Claude calls the tools and answers
with the real numbers and a chart.

**B — Claude Desktop (local, stdio).** Add this to `claude_desktop_config.json`
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

### Deploy to Google Cloud Run

The `Dockerfile` (`python:3.12-slim`) installs `mcp_server/requirements.txt` + chromium (kaleido
renders chart PNGs), and bakes in only the small data files — `.dockerignore` keeps the 30MB
CSV, dashboard code, and dev tooling out of the build context. Build from the **repo root** so
`--source .` can reach `core.py` and `data/outputs/`:

```
gcloud run deploy budgetair-mcp --source . --region europe-west4 --allow-unauthenticated \
  --cpu 2 --memory 1Gi
```

Cloud Run prints a public HTTPS URL; the MCP endpoint is that URL + `/mcp`. Re-certify against
it: `python eval/golden_eval.py --url https://<your-url>/mcp --out eval/scorecard_deployed.md`.

- **Keep `--cpu 2 --memory 1Gi`.** Chart PNGs need a headless chromium; on the default
  1 vCPU / 512 MiB it and the web-server event loop fight over one core and the request *hangs*.
  Two vCPUs render a chart in ~10s cold. This is instance *sizing*, not `--min-instances`, so the
  service still **scales to zero (€0 idle)**. A bare `--source .` redeploy resets sizing and
  re-breaks rendering — always pass these flags.
- **Cost.** Scale-to-zero = €0/month at this traffic; the only cost is a few-second cold start
  on the first request after ~15 idle minutes. For a demo day, keep one instance warm
  (~€3–5/month): `gcloud run services update budgetair-mcp --region europe-west4 --min-instances 1`,
  and revert afterwards with `--min-instances 0`.

> **Security:** this demo is public and read-only on fictional case data. A production
> deployment would sit behind OAuth with per-user scopes.

## Deliverables

- `data/outputs/orders_compiled_enriched.csv` — order-level fact table (auditable).
- `data/outputs/impact_summary.csv` — month × channel × zone rollup (analysis-ready).
- `analysis.py` — reproducible pipeline; `CLAUDE.md` — locked assumptions + validated numbers.
- Deployed **dashboard** + **MCP server** for AI-powered Q&A (links at the top).
