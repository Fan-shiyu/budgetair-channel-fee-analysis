"""Home / executive summary — 'What the fee change really cost us'."""
import streamlit as st

import utils as u

u.page_setup("Home")

st.title("What the new Aeroprice fee really cost us")
u.md(
    "**On the orders we actually sold in 2022, the partner's 'cheaper' new fee "
    f"would have cost us {u.fmt_usd(u.full_year_delta(), signed=True)} more — "
    "because a brand-new $10.50 minimum fee landed on the cheap tickets that make "
    "up most of the channel.**"
)

# --- Headline KPI cards (always the full validated figures, computed) --------
cheap_share = u.load_zone_summary().set_index("zone_plain").loc["Pays more", "share_pct"]
ae_change = u.aeroprice_cheap_change() * 100
control_change = u._cheap_change(u.CONTROL_CHANNEL) * 100
min_fee = u.NEW_SCHEME["floor"]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Extra cost, full year", u.fmt_usd(u.full_year_delta(), signed=True),
          help="New fee minus old fee, applied to every 2022 Aeroprice order — same orders, both price schemes.")
c2.metric("Orders that now pay more", u.fmt_pct(cheap_share),
          help="Share of Aeroprice orders whose fee went up under the new terms.")
c3.metric("Cheap-fare orders lost", u.fmt_pct(ae_change, signed=True),
          delta=f"vs {u.fmt_pct(control_change, signed=True)} on a channel with no fee change",
          delta_color="off",
          help="Change in Aeroprice cheap-ticket volume from summer to the last quarter of 2022.")
c4.metric("Saved per order moved to Direct", f"${min_fee:,.2f}",
          help="Every cheap order we sell on our own Direct site avoids at least the new $10.50 minimum partner fee.")

st.divider()

# --- The four-sentence storyline (numbers injected, never hardcoded) ---------
st.subheader("The story in four sentences")
u.md(
    f"1. **The new contract looks cheaper** — a lower percentage and a lower ceiling — "
    f"but its brand-new ${min_fee:,.2f} minimum fee lands on **{u.fmt_pct(cheap_share)}** of "
    f"the channel's orders, cheap tickets that were already barely profitable.\n\n"
    f"2. **On the sales mix we actually had, it costs {u.fmt_usd(u.full_year_delta(), signed=True)} a year.** "
    f"On today's post-change mix it looks roughly cost-neutral — but only because the punished "
    f"cheap-fare segment had already walked away.\n\n"
    f"3. **Cheap fares collapsed in Aeroprice ({u.fmt_pct(ae_change, signed=True)})** while a "
    f"comparable channel with no fee change barely moved ({u.fmt_pct(control_change, signed=True)}). "
    f"Most of that lost demand was **not** recaptured by our other channels — it likely went to competitors.\n\n"
    f"4. **What to do:** stop competing on sub-${u.BREAKEVEN:,.0f} fares inside Aeroprice (they lose money there), "
    f"reinvest the saving on expensive fares into sharper prices, make our own Direct site the home for budget "
    f"fares (every captured order saves at least ${min_fee:,.2f} in fees), and use the full-year number to "
    f"renegotiate a tiered fee."
)

st.divider()

# --- Page links -------------------------------------------------------------
st.subheader("Walk through the evidence")
st.page_link("pages/1_The_Fee_Change.py", label="1 · The fee change — who pays more, who pays less", icon="🔀")
st.page_link("pages/2_Overall_Impact.py", label="2 · Overall impact — the full-year bill", icon="💵")
st.page_link("pages/3_Winners_and_Losers.py", label="3 · Winners & losers — by airline, route and price", icon="⚖️")
st.page_link("pages/4_What_Happened.py", label="4 · What happened after October 1", icon="📉")
st.page_link("pages/5_Direct_Opportunity.py", label="5 · The Direct opportunity — winning fares back", icon="🎯")

u.caption("Every number on this dashboard is recomputed from the 2022 order data each time the page loads.")
