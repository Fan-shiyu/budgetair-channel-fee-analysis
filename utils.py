"""Shared helpers for the BudgetAir channel-fee dashboard.

Everything the app displays is COMPUTED at runtime from the CSVs in data/outputs.
The only literal numbers allowed in this codebase are:
  1. the fee-contract terms (OLD/NEW scheme, break-evens, change date) below, and
  2. the EXPECTED dict inside verify_numbers(), which is a TEST, not display text.
No page may hardcode a result figure.
"""
from pathlib import Path

import numpy as np
import pandas as pd
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
}


# --------------------------------------------------------------------------- #
# Fee maths + formatting
# --------------------------------------------------------------------------- #
def fee_curve(ticket, rate, floor, cap):
    """Channel fee for a ticket value under one scheme: clip(rate*ticket, floor, cap)."""
    return np.clip(np.asarray(ticket, dtype=float) * rate, floor, cap)


def fmt_usd(x, signed=False):
    """Whole-dollar string, e.g. '$131,696' or '+$131,696' / '-$1,768'."""
    x = float(x)
    sign = ""
    if signed:
        sign = "+" if x >= 0 else "-"
    elif x < 0:
        sign = "-"
    return f"{sign}${abs(x):,.0f}"


def fmt_pct(x, signed=False):
    """One-decimal percent string. Pass x as a percentage already (e.g. 12.5)."""
    x = float(x)
    sign = "+" if (signed and x >= 0) else ("-" if x < 0 else "")
    return f"{sign}{abs(x):.1f}%"


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


def aeroprice_cheap_change():
    """Aeroprice cheap-fare volume change: Jul-Sep avg -> Oct-Dec avg (fraction)."""
    return _cheap_change(CHANNEL)


def _cheap_change(channel):
    m = load_monthly_cheap_by_channel()
    row = m[m["Channel"] == channel].set_index("month")["orders"]
    pre = row.reindex([7, 8, 9]).mean()
    post = row.reindex([10, 11, 12]).mean()
    return (post - pre) / pre


# --------------------------------------------------------------------------- #
# Self-check: recompute headline figures, warn if data & slides have drifted.
# EXPECTED is the single place a result literal may appear (this is a TEST).
# --------------------------------------------------------------------------- #
EXPECTED = {
    "full_year_delta": 131696.0,
    "q4_delta": -1768.0,
    "floor_zone_avg": 6.41,
    "aeroprice_cheap_change": -0.585,
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
            f"- **{k}**: slides say {v:,.2f}, data now says {a:,.2f}" for k, v, a in drift
        )
        st.warning(
            "Heads up — the numbers below no longer match the validated figures in the "
            "case notes. The data and the slides have drifted apart:\n" + lines
        )


# --------------------------------------------------------------------------- #
# Shared page furniture
# --------------------------------------------------------------------------- #
def page_setup(title):
    st.set_page_config(page_title="BudgetAir — Fee Change", page_icon="✈️", layout="wide")
    drift_banner()


def md(text):
    """st.markdown with '$' escaped — otherwise Streamlit reads $...$ as LaTeX math."""
    st.markdown(text.replace("$", "\\$"))


def caption(text):
    st.caption(text.replace("$", "\\$"))


# Plotly config: keep the toolbar (PNG download) — the user screenshots charts.
PLOTLY_CONFIG = {"displayModeBar": True, "displaylogo": False}
