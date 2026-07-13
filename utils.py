"""Streamlit-facing helpers for the BudgetAir dashboard.

All pure logic (constants, data loaders, headline metrics, the Plotly template, and
the chart builders) lives in `core.py` and is re-exported here, so the dashboard and
the MCP server share ONE definition. This module adds only the Streamlit rendering
helpers (which import streamlit); the MCP server imports `core`, never this module.
"""
import re

import streamlit as st

from core import *  # noqa: F401,F403  constants, loaders, metrics, style_fig, builders, PLOTLY_CONFIG


# --------------------------------------------------------------------------- #
# Chart rendering (Streamlit)
# --------------------------------------------------------------------------- #
def show(fig):
    """Render an already-styled figure (e.g. from a core.build_* builder)."""
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)


def chart(fig, title, height=440, xgrid=False, ygrid=True):
    """Style a raw figure and render it (for page-specific charts not in core)."""
    st.plotly_chart(style_fig(fig, title, height, xgrid, ygrid),
                    use_container_width=True, config=PLOTLY_CONFIG)


# --------------------------------------------------------------------------- #
# Self-check banner
# --------------------------------------------------------------------------- #
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
