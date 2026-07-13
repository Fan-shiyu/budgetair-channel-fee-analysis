"""Shared helpers for the BudgetAir channel-fee dashboard.

Everything the app displays is COMPUTED at runtime from the CSVs in data/outputs.
The only literal numbers allowed in this codebase are:
  1. the fee-contract terms (OLD/NEW scheme, break-evens, change date) below, and
  2. the EXPECTED dict inside verify_numbers(), which is a TEST, not display text.
No page may hardcode a result figure.
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# --------------------------------------------------------------------------- #
# Paths  (the deliverable CSVs live under data/outputs, not a root outputs/)
# --------------------------------------------------------------------------- #
BASE_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = BASE_DIR / "data" / "outputs"
APP_DATA_DIR = OUTPUTS_DIR / "app_data"
SUMMARY_CSV = OUTPUTS_DIR / "impact_summary.csv"

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


# --------------------------------------------------------------------------- #
# Fee maths + formatting
# --------------------------------------------------------------------------- #
def fee_curve(ticket, rate, floor, cap):
    """Channel fee for a ticket value under one scheme: clip(rate*ticket, floor, cap)."""
    return np.clip(np.asarray(ticket, dtype=float) * rate, floor, cap)


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
# Cached loaders  (app reads ONLY these small files, never the 30MB order file)
# --------------------------------------------------------------------------- #
def _month_num(series):
    return series.astype(str).str[5:7].astype(int)


@st.cache_data
def load_summary():
    """month x Channel x ticket_zone rollup (impact_summary.csv)."""
    df = pd.read_csv(SUMMARY_CSV)
    df["month"] = _month_num(df["sales_month"])
    return df


@st.cache_data
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


@st.cache_data
def load_stats():
    """A few scalar stats that needed the order-level file, as a {stat: value} dict."""
    df = load_app_csv("headline_stats.csv")
    return dict(zip(df["stat"], df["value"]))


# --------------------------------------------------------------------------- #
# Headline metrics recomputed from data  (feeds both the pages and the check)
# --------------------------------------------------------------------------- #
def aeroprice_summary(period="full"):
    """Aeroprice rows of the summary, optionally restricted to a period.

    period: 'full' (all 2022), 'q4' (Oct-Dec), 'pre' (Jan-Sep).
    """
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
    (total Aeroprice cheap orders) / (total cheap orders, all channels). Pooled, so
    high-volume months count for more than low-volume ones (fraction, e.g. 0.726)."""
    ae = _monthly_cheap(CHANNEL).reindex(months).sum()
    allc = _monthly_cheap("All channels").reindex(months).sum()
    return ae / allc


# --------------------------------------------------------------------------- #
# Self-check: recompute headline figures, warn if data & slides have drifted.
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

    Empty list == data still reproduces the validated headline numbers.
    """
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


def drift_banner():
    """Render an st.warning banner on any page if the data has drifted from slides."""
    drift = verify_numbers()
    if drift:
        lines = "\n".join(
            f"- **{k}**: slides say {v:,.3f}, data now says {a:,.3f}" for k, v, a in drift
        )
        st.warning(
            "Heads up — the numbers below no longer match the validated figures in the "
            "case notes. The data and the slides have drifted apart:\n" + lines
        )


# --------------------------------------------------------------------------- #
# One shared Plotly look, registered once and applied to every figure
# --------------------------------------------------------------------------- #
pio.templates["budgetair"] = go.layout.Template(layout=dict(
    font=dict(family=CHART_FONT, size=13, color="#374151"),
    title=dict(font=dict(family=CHART_FONT, size=18, color=COLORS["ink"]),
               x=0, xanchor="left", y=0.92, yanchor="top"),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    xaxis=dict(showgrid=False, zeroline=False, showline=False, ticks="",
               title=dict(font=dict(size=12, color=COLORS["muted"])),
               tickfont=dict(size=12, color=COLORS["muted"])),
    yaxis=dict(showgrid=True, gridcolor=COLORS["grid"], zeroline=False, showline=False,
               title=dict(font=dict(size=12, color=COLORS["muted"])),
               tickfont=dict(size=12, color=COLORS["muted"])),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                font=dict(size=12, color="#374151")),
    colorway=[COLORS["brand"], COLORS["more"], COLORS["less"], COLORS["neutral"]],
    # generous top margin so titles clear the Plotly toolbar; right margin so
    # outside bar-value labels are never clipped at the plot edge.
    margin=dict(t=96, r=90, b=52, l=64),
))

# Plotly config: keep the toolbar (PNG download) — the user screenshots charts.
PLOTLY_CONFIG = {"displayModeBar": True, "displaylogo": False,
                 "modeBarButtonsToRemove": ["lasso2d", "select2d"]}


def style_fig(fig, title, height=440, xgrid=False, ygrid=True):
    """Apply the shared template so every chart reads as one family."""
    fig.update_layout(template="budgetair", title=dict(text=title), height=height)
    fig.update_xaxes(showgrid=xgrid, gridcolor=COLORS["grid"])
    fig.update_yaxes(showgrid=ygrid, gridcolor=COLORS["grid"])
    return fig


def chart(fig, title, height=440, xgrid=False, ygrid=True):
    """Style a figure and render it with the standard config."""
    st.plotly_chart(style_fig(fig, title, height, xgrid, ygrid),
                    use_container_width=True, config=PLOTLY_CONFIG)


# --------------------------------------------------------------------------- #
# Page furniture: global CSS, sidebar branding, header pattern, KPI cards
# --------------------------------------------------------------------------- #
_GLOBAL_CSS = """
<style>
  section.main div.block-container {max-width: 1150px; padding-top: 2.2rem;
        padding-bottom: 3rem;}
  h1 {letter-spacing: -0.02em; font-weight: 700;}
  .ba-subtitle {font-size: 1.14rem; line-height: 1.55; color: #6b7280;
        font-weight: 400; margin: -0.2rem 0 0.2rem 0;}
  .ba-subtitle strong {color: #374151; font-weight: 600;}
  hr {margin: 1.25rem 0 1.4rem 0;}
  /* replace the default page nav with our branded one */
  [data-testid="stSidebarNav"] {display: none;}
  [data-testid="stSidebar"] .ba-brand {font-weight: 700; font-size: 1.02rem;
        color: #1B6CB0; margin-bottom: 0.1rem;}
  div[data-testid="stMetric"] {padding: 0.1rem 0.1rem;}
  /* let KPI labels wrap instead of truncating with an ellipsis */
  [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {
        white-space: normal !important; overflow: visible !important;
        text-overflow: clip !important;}
  /* equal-height KPI cards: size to the tallest variant, content top-aligned,
     so every KPI row has one clean bottom edge regardless of delta chips */
  [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] > [data-testid="stMetric"]) {
        min-height: 148px; justify-content: flex-start;}
</style>
"""

_NAV = [
    ("app.py", "Overview", "🏠"),
    ("pages/1_The_Fee_Change.py", "The Fee Change", "🔀"),
    ("pages/2_Overall_Impact.py", "Overall Impact", "💵"),
    ("pages/3_Winners_and_Losers.py", "Winners & Losers", "⚖️"),
    ("pages/4_What_Happened.py", "What Happened", "📉"),
    ("pages/5_Direct_Opportunity.py", "Direct Opportunity", "🎯"),
]


def page_setup(nav_title, icon="✈️"):
    st.set_page_config(page_title=f"{nav_title} · BudgetAir", page_icon=icon, layout="wide")
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)
    with st.sidebar:
        st.markdown('<div class="ba-brand">BudgetAir · Fee Change Analysis</div>',
                    unsafe_allow_html=True)
        st.caption("2022 orders · Aeroprice contract change Oct 1")
        st.divider()
        for path, label, ic in _NAV:
            st.page_link(path, label=label, icon=ic)
    drift_banner()


def header(title, subtitle):
    """Finding-style H1 + a muted one-sentence takeaway + a divider."""
    st.title(title)
    s = subtitle.replace("$", "&#36;")                       # keep $ literal in HTML
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)  # honour **bold**
    st.markdown(f'<p class="ba-subtitle">{s}</p>', unsafe_allow_html=True)
    st.divider()


def kpi(col, label, value, delta=None, delta_color="normal", help=None):
    """One KPI rendered as a bordered card in the given column."""
    with col.container(border=True):
        st.metric(label, value, delta=delta, delta_color=delta_color, help=help)


def md(text):
    """st.markdown with '$' escaped — otherwise Streamlit reads $...$ as LaTeX math."""
    st.markdown(text.replace("$", "\\$"))


def caption(text):
    st.caption(text.replace("$", "\\$"))
