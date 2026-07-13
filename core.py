"""Streamlit-free shared core for the BudgetAir channel-fee analysis.

Both the Streamlit dashboard (via utils.py) and the MCP server import from here, so
there is ONE definition of the fee constants, the data loaders, the headline metrics,
the chart look, and the chart builders. Nothing in this module imports streamlit.

The only literal numbers permitted anywhere are the fee-contract terms below and the
EXPECTED dict in verify_numbers() (a TEST, not display text).
"""
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
BASE_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = BASE_DIR / "data" / "outputs"
APP_DATA_DIR = OUTPUTS_DIR / "app_data"
MCP_DATA_DIR = OUTPUTS_DIR / "mcp_data"
SUMMARY_CSV = OUTPUTS_DIR / "impact_summary.csv"
SEGMENTS_PARQUET = MCP_DATA_DIR / "segments.parquet"

# --------------------------------------------------------------------------- #
# Contract terms from the case (the ONLY permitted numeric constants)
# --------------------------------------------------------------------------- #
OLD_SCHEME = {"rate": 0.040, "floor": 0.00, "cap": 24.00}   # before 2022-10-01
NEW_SCHEME = {"rate": 0.038, "floor": 10.50, "cap": 19.00}  # from 2022-10-01
BREAKEVEN = 262.50          # below this a ticket pays MORE under the new terms
CAP_MIN = 500.00            # above this the new cap starts to bind
CHANGE_DATE = "2022-10-01"
CHANGE_MONTH = 10           # October = first month under the new fee
PRE_MONTHS = list(range(1, 10))    # Jan-Sep, before the change
POST_MONTHS = [10, 11, 12]         # Oct-Dec, after the change
SUMMER_MONTHS = [7, 8, 9]          # Jul-Sep, the pre-change baseline for volume

CHANNEL = "Aeroprice"       # the only channel with contractual fee terms
CONTROL_CHANNEL = "Google Flights"   # comparable channel with NO fee change
DIRECT_CHANNEL = "Direct"

# Exact ticket-zone label strings as written in the CSVs, in commercial order.
ZONE_CHEAP = "<$262.50 (fee up)"
ZONE_MID = "$262.50-500 (about even)"
ZONE_CAP = ">$500 (fee down)"
ZONES = [ZONE_CHEAP, ZONE_MID, ZONE_CAP]
ZONE_PLAIN = {ZONE_CHEAP: "Pays more", ZONE_MID: "About even", ZONE_CAP: "Pays less"}

# IATA carrier code -> airline name (labels only, for readable charts)
CARRIER_NAMES = {
    "LA": "LATAM", "F9": "Frontier", "AS": "Alaska", "TK": "Turkish",
    "AV": "Avianca", "EI": "Aer Lingus", "NK": "Spirit", "AM": "Aeromexico",
    "QR": "Qatar", "EK": "Emirates", "UA": "United", "LH": "Lufthansa",
    "DL": "Delta", "AA": "American", "B6": "JetBlue", "WN": "Southwest",
    "IB": "Iberia", "AF": "Air France", "KL": "KLM", "BA": "British Airways",
}

# Colour language: red = pays more / loses, green = pays less / wins, grey = neutral.
COLORS = {
    "more": "#C0392B",   # red
    "less": "#2E7D32",   # green
    "neutral": "#7F8C8D",  # grey
    "brand": "#1B6CB0",  # brand blue
    "old": "#7F8C8D",
    "new": "#1B6CB0",
    "ink": "#262730",    # chart title / dark text
    "muted": "#6b7280",  # axis / muted text
    "grid": "#e5e7eb",   # gridlines
}

CHART_FONT = "Source Sans Pro, sans-serif"   # matches Streamlit's default UI font

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# --------------------------------------------------------------------------- #
# Fee maths + formatting
# --------------------------------------------------------------------------- #
def fee_curve(ticket, rate, floor, cap):
    """Channel fee for a ticket value under one scheme: clip(rate*ticket, floor, cap)."""
    return np.clip(np.asarray(ticket, dtype=float) * rate, floor, cap)


def binding_rule(ticket, scheme):
    """Which rule sets the fee for this ticket under a scheme: 'floor', 'percent', 'cap'."""
    raw = ticket * scheme["rate"]
    if raw <= scheme["floor"]:
        return "floor"
    if raw >= scheme["cap"]:
        return "cap"
    return "percent"


def fmt_usd(x, signed=False, cents=False):
    """Dollar string. Whole dollars by default ('+$131,696'); cents=True for small
    per-order amounts ('+$2.85') where whole-dollar rounding would distort."""
    x = float(x)
    sign = ("+" if x >= 0 else "-") if signed else ("-" if x < 0 else "")
    dec = 2 if cents else 0
    return f"{sign}${abs(x):,.{dec}f}"


def fmt_pct(x, signed=False, decimals=1):
    """Percent string; pass x already as a percentage (e.g. 12.5)."""
    x = float(x)
    sign = "+" if (signed and x >= 0) else ("-" if x < 0 else "")
    return f"{sign}{abs(x):.{decimals}f}%"


def fmt_pp(x, signed=True):
    """Percentage-point string, e.g. '+1.6 pp' / '-21.5 pp'."""
    x = float(x)
    sign = "+" if (signed and x >= 0) else ("-" if x < 0 else "")
    return f"{sign}{abs(x):.1f} pp"


# --------------------------------------------------------------------------- #
# Cached loaders  (small files only; the 30MB order CSV is never read here)
# lru_cache keeps one canonical frame per process; callers copy before mutating.
# --------------------------------------------------------------------------- #
def _month_num(series):
    return series.astype(str).str[5:7].astype(int)


@lru_cache(maxsize=None)
def load_summary():
    """month x Channel x ticket_zone rollup (impact_summary.csv)."""
    df = pd.read_csv(SUMMARY_CSV)
    df["month"] = _month_num(df["sales_month"])
    return df


@lru_cache(maxsize=None)
def load_app_csv(name):
    """Load one prepared chart-ready CSV from data/outputs/app_data/."""
    return pd.read_csv(APP_DATA_DIR / name)


def load_carrier_impact():
    return load_app_csv("carrier_impact.csv")


def load_dimension_impact():
    return load_app_csv("dimension_impact.csv")


def load_monthly_cheap_by_channel():
    return load_app_csv("monthly_cheap_by_channel.csv")


def load_aeroprice_monthly():
    return load_app_csv("aeroprice_monthly.csv")


def load_direct_share():
    return load_app_csv("direct_share.csv")


def load_zone_summary():
    return load_app_csv("zone_summary.csv")


@lru_cache(maxsize=None)
def load_stats():
    """A few scalar stats that needed the order-level file, as a {stat: value} dict."""
    df = load_app_csv("headline_stats.csv")
    return dict(zip(df["stat"], df["value"]))


# --------------------------------------------------------------------------- #
# Headline metrics recomputed from data
# --------------------------------------------------------------------------- #
def aeroprice_summary(period="full"):
    """Aeroprice rows of the summary. period: 'full', 'q4' (Oct-Dec), 'pre' (Jan-Sep)."""
    df = load_summary()
    ae = df[df["Channel"] == CHANNEL]
    if period == "q4":
        ae = ae[ae["month"] >= CHANGE_MONTH]
    elif period == "pre":
        ae = ae[ae["month"] < CHANGE_MONTH]
    return ae


def zone_deltas(period="full"):
    """Total fee delta and order count per ticket zone for the chosen period."""
    ae = aeroprice_summary(period)
    g = ae.groupby("ticket_zone", observed=True).agg(
        orders=("orders", "sum"),
        total_delta=("fee_delta", "sum"),
    )
    g = g.reindex(ZONES)
    g["avg_delta"] = g["total_delta"] / g["orders"]
    return g


def full_year_delta():
    return aeroprice_summary("full")["fee_delta"].sum()


def q4_delta():
    return aeroprice_summary("q4")["fee_delta"].sum()


def floor_zone_avg():
    z = zone_deltas("full")
    return z.loc[ZONE_CHEAP, "total_delta"] / z.loc[ZONE_CHEAP, "orders"]


def _monthly_cheap(channel):
    m = load_monthly_cheap_by_channel()
    return m[m["Channel"] == channel].set_index("month")["orders"]


def cheap_volume_change(channel):
    """Cheap-fare volume change for a channel: Jul-Sep avg -> Oct-Dec avg (fraction)."""
    row = _monthly_cheap(channel)
    pre = row.reindex(SUMMER_MONTHS).mean()
    post = row.reindex(POST_MONTHS).mean()
    return (post - pre) / pre


def aeroprice_cheap_change():
    return cheap_volume_change(CHANNEL)


def cheap_share_pooled(months):
    """Aeroprice's POOLED share of all cheap-fare orders across the given months:
    (total Aeroprice cheap orders) / (total cheap orders, all channels)."""
    ae = _monthly_cheap(CHANNEL).reindex(list(months)).sum()
    allc = _monthly_cheap("All channels").reindex(list(months)).sum()
    return ae / allc


def total_cheap_monthly(months):
    """Average per-month total cheap-fare orders across ALL channels for the months."""
    return _monthly_cheap("All channels").reindex(list(months)).mean()


# --------------------------------------------------------------------------- #
# Self-check: recompute headline figures, refuse to serve stale data.
# EXPECTED is the single place a result literal may appear (this is a TEST).
# --------------------------------------------------------------------------- #
EXPECTED = {
    "full_year_delta": 131696.0,
    "q4_delta": -1768.0,
    "floor_zone_avg": 6.41,
    "aeroprice_cheap_change": -0.585,
    "cheap_share_pre_pooled": 0.726,
    "cheap_share_post_pooled": 0.511,
}


def verify_numbers(tol=0.01):
    """Return a list of (metric, expected, actual) for any figure off by > tol.
    Empty list == data still reproduces the validated headline numbers."""
    actual = {
        "full_year_delta": float(full_year_delta()),
        "q4_delta": float(q4_delta()),
        "floor_zone_avg": float(floor_zone_avg()),
        "aeroprice_cheap_change": float(aeroprice_cheap_change()),
        "cheap_share_pre_pooled": float(cheap_share_pooled(PRE_MONTHS)),
        "cheap_share_post_pooled": float(cheap_share_pooled(POST_MONTHS)),
    }
    drift = []
    for key, exp in EXPECTED.items():
        act = actual[key]
        denom = abs(exp) if exp else 1.0
        if abs(act - exp) / denom > tol:
            drift.append((key, exp, act))
    return drift


# --------------------------------------------------------------------------- #
# One shared Plotly look, registered once and applied to every figure
# --------------------------------------------------------------------------- #
pio.templates["budgetair"] = go.layout.Template(layout=dict(
    font=dict(family=CHART_FONT, size=13, color="#374151"),
    title=dict(font=dict(family=CHART_FONT, size=18, color=COLORS["ink"]),
               x=0, xanchor="left", y=0.92, yanchor="top"),
    paper_bgcolor="white",
    plot_bgcolor="white",
    xaxis=dict(showgrid=False, zeroline=False, showline=False, ticks="",
               title=dict(font=dict(size=12, color=COLORS["muted"])),
               tickfont=dict(size=12, color=COLORS["muted"])),
    yaxis=dict(showgrid=True, gridcolor=COLORS["grid"], zeroline=False, showline=False,
               title=dict(font=dict(size=12, color=COLORS["muted"])),
               tickfont=dict(size=12, color=COLORS["muted"])),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                font=dict(size=12, color="#374151")),
    colorway=[COLORS["brand"], COLORS["more"], COLORS["less"], COLORS["neutral"]],
    margin=dict(t=96, r=90, b=52, l=64),
))

# Plotly config for the dashboard's interactive charts (toolbar/PNG download).
PLOTLY_CONFIG = {"displayModeBar": True, "displaylogo": False,
                 "modeBarButtonsToRemove": ["lasso2d", "select2d"]}


def style_fig(fig, title, height=440, xgrid=False, ygrid=True):
    """Apply the shared template so every chart reads as one family."""
    fig.update_layout(template="budgetair", title=dict(text=title), height=height)
    fig.update_xaxes(showgrid=xgrid, gridcolor=COLORS["grid"])
    fig.update_yaxes(showgrid=ygrid, gridcolor=COLORS["grid"])
    return fig


def render_png(fig, width=900, height=None, scale=2):
    """Render a (styled) Plotly figure to PNG bytes via kaleido, for MCP image content."""
    h = height or fig.layout.height or 440
    return fig.to_image(format="png", width=width, height=int(h), scale=scale)


# --------------------------------------------------------------------------- #
# Chart builders — ONE definition, used by both the dashboard and the MCP server.
# Each returns a fully styled go.Figure (title baked in via style_fig).
# --------------------------------------------------------------------------- #
def build_fee_curve_fig(mark_ticket=None):
    """Old vs new fee by ticket price, with shaded pay-more/pay-less regions.
    Optionally mark a single ticket price."""
    tickets = np.linspace(0, 800, 400)
    old_fee = fee_curve(tickets, **OLD_SCHEME)
    new_fee = fee_curve(tickets, **NEW_SCHEME)
    fig = go.Figure()
    fig.add_vrect(x0=0, x1=BREAKEVEN, fillcolor=COLORS["more"], opacity=0.07, line_width=0)
    fig.add_vrect(x0=BREAKEVEN, x1=800, fillcolor=COLORS["less"], opacity=0.07, line_width=0)
    fig.add_trace(go.Scatter(x=tickets, y=old_fee, name="Old fee (before Oct 2022)",
                             line=dict(color=COLORS["old"], dash="dash", width=2)))
    fig.add_trace(go.Scatter(x=tickets, y=new_fee, name="New fee (from Oct 2022)",
                             line=dict(color=COLORS["new"], width=3)))
    fig.add_vline(x=BREAKEVEN, line_dash="dot", line_color="#444",
                  annotation_text=f"break-even ${BREAKEVEN:,.0f}", annotation_position="bottom right")
    fig.add_annotation(x=BREAKEVEN / 2, y=13, text="pays <b>MORE</b><br>under new terms",
                       showarrow=False, font=dict(color=COLORS["more"], size=13))
    fig.add_annotation(x=(BREAKEVEN + 800) / 2, y=13, text="pays <b>LESS</b>",
                       showarrow=False, font=dict(color=COLORS["less"], size=13))
    if mark_ticket is not None and 0 <= mark_ticket <= 800:
        o = float(fee_curve(mark_ticket, **OLD_SCHEME))
        n = float(fee_curve(mark_ticket, **NEW_SCHEME))
        fig.add_vline(x=mark_ticket, line_color=COLORS["ink"], line_width=2,
                      annotation_text=f"${mark_ticket:,.0f}: old {fmt_usd(o, cents=True)} → new {fmt_usd(n, cents=True)}",
                      annotation_position="top right")
    fig.update_xaxes(title_text="Ticket price (base fare + tax), $")
    fig.update_yaxes(title_text="Fee we pay per order, $", range=[0, 26])
    return style_fig(fig, f"The new fee only saves money above a ${BREAKEVEN:,.0f} ticket", height=460)


def build_monthly_delta_fig(highlight_months=None):
    """Aeroprice monthly total fee-delta bars, Oct-1 marker.
    highlight_months: optional list of month ints to emphasise (others dimmed)."""
    aem = load_aeroprice_monthly().sort_values("month")
    labels = [MONTH_NAMES[m - 1] for m in aem["month"]]
    base_colors = [COLORS["more"] if d > 0 else COLORS["less"] for d in aem["fee_delta"]]
    if highlight_months:
        opac = [1.0 if m in set(highlight_months) else 0.35 for m in aem["month"]]
    else:
        opac = [1.0] * len(aem)
    fig = go.Figure(go.Bar(
        x=labels, y=aem["fee_delta"], marker_color=base_colors, marker_opacity=opac,
        text=[fmt_usd(v, signed=True) for v in aem["fee_delta"]], textposition="outside"))
    fig.add_vline(x=8.5, line_dash="dot", line_color="#444",
                  annotation_text="new fee starts", annotation_position="top left")
    fig.update_yaxes(title_text="Extra fee that month, $")
    return style_fig(fig, "The extra cost was building all year until cheap fares left in October",
                     height=420)


# dimension enum -> (app_data source, plain label used in the chart title)
_DIM_MAP = {
    "airline": ("carrier", "airline"),
    "journey_type": ("Journey type", "journey type"),
    "domestic_international": ("Domestic vs International", "domestic vs international"),
    "ticket_zone": ("Ticket price zone", "ticket price zone"),
}


def winners_losers_table(dimension):
    """Return the ranked DataFrame (category, value=avg_delta, orders, total_delta) for a dimension."""
    if dimension == "airline":
        d = load_carrier_impact().rename(columns={"carrier": "category", "avg_delta": "value"})
        d = d[["category", "value", "orders", "total_delta"]]
    elif dimension in _DIM_MAP:
        view = _DIM_MAP[dimension][0]
        dim = load_dimension_impact()
        d = dim[dim["dimension"] == view].rename(columns={"avg_delta": "value"})
        d = d[["category", "value", "orders", "total_delta"]]
    else:
        raise ValueError(dimension)
    return d.sort_values("value", ascending=False).reset_index(drop=True)


def build_winners_losers_fig(dimension):
    """Red/green horizontal bars of avg fee delta per order for a dimension."""
    d = winners_losers_table(dimension).sort_values("value")
    label = _DIM_MAP[dimension][1]
    colors = [COLORS["more"] if v > 0 else COLORS["less"] for v in d["value"]]
    fig = go.Figure(go.Bar(
        x=d["value"], y=d["category"], orientation="h", marker_color=colors,
        text=[fmt_usd(v, signed=True, cents=True) for v in d["value"]],
        textposition="outside", cliponaxis=False))
    lo, hi = d["value"].min(), d["value"].max()
    pad = max(hi - lo, 1) * 0.18
    fig.update_xaxes(title_text="Change in fee per order, $", range=[min(lo, 0) - pad, hi + pad])
    fig.update_layout(margin=dict(l=150))
    height = 520 if dimension == "airline" else 430
    return style_fig(fig, f"Average change in fee per order, by {label} (red = pays more, green = pays less)",
                     height=height, xgrid=True, ygrid=False)


def build_channel_trends_fig():
    """Cheap-fare volume: Aeroprice vs control channel, indexed to Jul-Sep avg = 100."""
    ae = _monthly_cheap(CHANNEL)
    gf = _monthly_cheap(CONTROL_CHANNEL)
    base_ae = ae.reindex(SUMMER_MONTHS).mean()
    base_gf = gf.reindex(SUMMER_MONTHS).mean()
    months = list(range(6, 13))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[MONTH_NAMES[i - 1] for i in months],
                             y=[ae.loc[i] / base_ae * 100 for i in months],
                             name="Aeroprice (fee changed)",
                             line=dict(color=COLORS["more"], width=3), mode="lines+markers"))
    fig.add_trace(go.Scatter(x=[MONTH_NAMES[i - 1] for i in months],
                             y=[gf.loc[i] / base_gf * 100 for i in months],
                             name="Comparable channel (no fee change)",
                             line=dict(color=COLORS["neutral"], width=2, dash="dash"),
                             mode="lines+markers"))
    fig.add_vline(x=3.5, line_dash="dot", line_color="#444",
                  annotation_text="new fee starts", annotation_position="top left")
    fig.update_yaxes(title_text="Cheap-fare orders (Jul–Sep average = 100)")
    return style_fig(fig, "Cheap-fare orders collapsed in Aeroprice but held steady where the fee didn't change")


def direct_trend():
    """Fit Direct's cheap-share trend on Jan-Sep, project through Dec.
    Returns (dataframe with projected col, dec_actual, dec_proj)."""
    ds = load_direct_share().sort_values("month").copy()
    pre = ds[ds["month"] <= 9]
    slope, intercept = np.polyfit(pre["month"], pre["share_pct"], 1)
    ds["projected"] = slope * ds["month"] + intercept
    dec_actual = ds.set_index("month").loc[12, "share_pct"]
    dec_proj = ds.set_index("month").loc[12, "projected"]
    return ds, float(dec_actual), float(dec_proj)


def build_direct_share_fig():
    """Direct's cheap-fare share vs its Jan-Sep trend projection, gap shaded."""
    ds, _, _ = direct_trend()
    xs = [MONTH_NAMES[m - 1] for m in ds["month"]]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=ds["projected"], name="If the old trend had continued",
                             line=dict(color=COLORS["neutral"], width=2, dash="dash")))
    fig.add_trace(go.Scatter(x=xs, y=ds["share_pct"], name="Direct's actual share",
                             line=dict(color=COLORS["less"], width=3), mode="lines+markers",
                             fill="tonexty", fillcolor="rgba(46,125,50,0.12)"))
    fig.add_vline(x=8.5, line_dash="dot", line_color="#444",
                  annotation_text="new fee starts", annotation_position="top left")
    fig.update_yaxes(title_text="Direct's share of all cheap-fare orders, %")
    return style_fig(fig, "Since the fee change, Direct is winning a bigger slice of budget fares than its trend predicted")
