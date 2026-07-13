"""FastMCP server for the BudgetAir channel-fee analysis.

The server owns the facts: each tool answers one category of business question with
deterministic Python and returns a text envelope (+ a chart PNG). The LLM only picks a
tool and narrates. Run it on HTTP (remote) or stdio (Claude Desktop):

    python -m mcp_server.server --transport http --port 8000
    python -m mcp_server.server --transport stdio
"""
import argparse
import logging
import os
import sys
from typing import Literal, Optional

from fastmcp import FastMCP

import core
from mcp_server import tools as T

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("budgetair-mcp")

INSTRUCTIONS = """\
This server answers questions about BudgetAir's 2022 Aeroprice channel-fee change for
NON-TECHNICAL business managers. Explain everything in plain English and always give the
dollar impact.

Ground rules:
- Only state numbers that appear in a tool's output. NEVER estimate, forecast, do your own
  arithmetic, or invent illustrative example calculations (e.g. do not make up "a $200 ticket
  would pay $8"). If you want an example, use fee_for_ticket to get real numbers. If the tools
  cannot answer, say so plainly and point the user to the dashboard — do not guess.
- Each tool returns HEADLINE / DATA / FACTS / CAVEATS / META and often a chart. Base your
  answer on the FACTS sentences (they are already correct); paraphrase, don't invent.
- Fee terms are known ONLY for Aeroprice. Other channels' fees are not in the data — if
  asked, say so (assumption A5).
- The data is 2022 only. There is no 2023/forecast tool; decline forecast questions.

Routing:
- Vague or general ("how bad was it?", "summary for my director") -> get_overview.
- The cost/impact for a period -> get_fee_impact.
- The fee on a specific ticket price -> fee_for_ticket.
- Comparisons across a dimension (airlines, journey type, domestic/intl, price zone) -> winners_losers.
- What happened to volume after the change -> channel_trends.
- The Direct-site win-back opportunity / savings -> direct_opportunity.
- Depth on one slice (a carrier, channel, zone, month, etc.) -> segment_detail.
- "Which month was worst/best for cheap fares" -> channel_trends (it reports the peak and
  lowest cheap-fare months by name and volume).
- "Why $262.50 / how was this computed?" -> get_methodology.
- Unsure which values are valid inputs -> get_data_catalog.
"""


def verify_gate():
    """Refuse to serve if the data no longer reproduces the validated headline numbers."""
    drift = core.verify_numbers()
    if drift:
        lines = "\n".join(f"  - {k}: expected {v:.4f}, data now {a:.4f}" for k, v, a in drift)
        log.error("DATA CONSISTENCY CHECK FAILED — refusing to start.\n%s", lines)
        raise SystemExit(1)
    log.info("Data consistency check passed (verify_numbers): headline numbers reproduce.")


mcp = FastMCP(name="BudgetAir Channel-Fee Analysis", instructions=INSTRUCTIONS)


@mcp.tool
def get_overview():
    """Executive summary of the whole fee change: what it cost for the full year, how many
    orders pay more, the cheap-fare volume drop vs a control channel, and the 4-sentence
    storyline. Use for vague or 'give me the headline' questions. No inputs."""
    return T.get_overview().to_content()


@mcp.tool
def get_fee_impact(period: str = "full_year"):
    """What the fee change cost for a period, as a like-for-like counterfactual (same orders,
    both fee schemes). Returns old/new/change in dollars, per order, and as a share of margin.
    period: 'full_year', 'before_change' (Jan–Sep), 'after_change' (Oct–Dec), or a single
    month '2022-01' … '2022-12'."""
    return T.get_fee_impact(period).to_content()


@mcp.tool
def fee_for_ticket(ticket_price: float):
    """The old vs new fee on one ticket price, which rule sets each fee (minimum / percentage /
    cap), and a plain verdict ('pays $6.50 MORE'). ticket_price is a number from 1 to 20,000."""
    return T.fee_for_ticket(ticket_price).to_content()


@mcp.tool
def winners_losers(
    dimension: Literal["airline", "journey_type", "domestic_international", "ticket_zone"] = "airline",
):
    """Who pays more and who pays less, ranked, for one dimension. Use 'ticket_zone' for
    cheap tickets (under $262.50) vs expensive / long-haul tickets (over $500), 'airline' by
    carrier, 'journey_type' for one-way vs return, 'domestic_international' by geography. Names
    the biggest loser and winner with the average dollar change per order and the order volume."""
    return T.winners_losers(dimension).to_content()


@mcp.tool
def channel_trends():
    """What happened to cheap-fare volume after the change: Aeroprice vs a comparable channel
    with no fee change, the pooled cheap-fare share shift, how much total cheap-fare demand was
    lost across all channels, AND which month was worst (lowest) and best (peak) for Aeroprice
    cheap fares, by name and volume. Use this for 'which month was worst/best for cheap fares'.
    No inputs."""
    return T.channel_trends().to_content()


@mcp.tool
def direct_opportunity(orders_per_month: int = 0):
    """The opportunity to win budget fares back on our own Direct site. With no input it
    describes the situation (Direct's share vs its trend). Give orders_per_month (0–2,200) to
    get the annual fee saving = orders × 12 × the average new Aeroprice fee on a cheap fare."""
    return T.direct_opportunity(orders_per_month).to_content()


@mcp.tool
def segment_detail(
    channel: Optional[str] = None,
    period: Optional[str] = None,
    ticket_zone: Optional[str] = None,
    carrier: Optional[str] = None,
    journey_type: Optional[str] = None,
    domestic_international: Optional[str] = None,
):
    """Deep dive on one slice of orders. All filters optional and combinable: channel,
    period (as in get_fee_impact), ticket_zone ('Pays more'/'About even'/'Pays less'),
    carrier (code or airline name), journey_type ('One Way'/'Return'),
    domestic_international ('Domestic'/'International'). Returns the normalized filters, a
    volume block, a fee block for the Aeroprice orders in the slice (benchmarked against the
    Aeroprice average), and a before/after split when the period spans Oct 1. Unknown or empty
    filters return the valid options so you can retry."""
    return T.segment_detail(channel, period, ticket_zone, carrier,
                            journey_type, domestic_international).to_content()


@mcp.tool
def get_methodology():
    """Plain-English methodology: the locked assumptions (A1–A5), why 'cheap fare' is under
    $262.50 (the break-even where the new $10.50 minimum equals 4%), the counterfactual method,
    the control-channel logic, and the data scope. No inputs."""
    return T.get_methodology().to_content()


@mcp.tool
def get_data_catalog():
    """The valid input values: channels, carriers (with order counts), months, ticket zones,
    journey types, and winners_losers dimensions, plus the total order count and data version.
    Call this if unsure which values a tool will accept. No inputs."""
    return T.get_data_catalog().to_content()


def main():
    parser = argparse.ArgumentParser(description="BudgetAir channel-fee MCP server")
    parser.add_argument("--transport", choices=["http", "stdio"],
                        default=os.environ.get("MCP_TRANSPORT", "http"))
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    args = parser.parse_args()

    verify_gate()   # refuse to start on drifted data

    if args.transport == "stdio":
        log.info("Starting MCP server on stdio")
        mcp.run(transport="stdio")
    else:
        log.info("Starting MCP server on http://%s:%s/mcp", args.host, args.port)
        mcp.run(transport="http", host=args.host, port=args.port)


if __name__ == "__main__":
    sys.exit(main())
