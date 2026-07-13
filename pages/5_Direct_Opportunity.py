"""Page 5 — The Direct opportunity: winning budget fares back on our own site."""
import numpy as np
import plotly.graph_objects as go
import streamlit as st

import utils as u

u.page_setup("Direct Opportunity", "🎯")

MN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

ds = u.load_direct_share().sort_values("month")
# fit a straight-line trend on the pre-change months (1-9) and project 10-12
pre = ds[ds["month"] <= 9]
slope, intercept = np.polyfit(pre["month"], pre["share_pct"], 1)
ds["projected"] = slope * ds["month"] + intercept
dec_actual = ds.set_index("month").loc[12, "share_pct"]
dec_proj = ds.set_index("month").loc[12, "projected"]

# displaced cheap-fare orders / month not recaptured = Aeroprice's monthly cheap-fare loss
ae = u.load_monthly_cheap_by_channel()
ae = ae[ae["Channel"] == u.CHANNEL].set_index("month")["orders"]
displaced = int(round(ae.reindex(u.SUMMER_MONTHS).mean() - ae.reindex(u.POST_MONTHS).mean()))
avg_cheap_fee = u.load_stats()["avg_cheap_fee_new"]

u.header(
    "Our own Direct site is the cheapest place to sell a budget fare",
    f"**Cheap fares are already drifting to Direct — by December it reached {u.fmt_pct(dec_actual)} "
    f"of cheap-fare orders, ahead of its {u.fmt_pct(dec_proj)} trend. Every budget order we win back "
    f"there avoids at least ${avg_cheap_fee:,.2f} in partner fees.**",
)

c1, c2 = st.columns(2)
u.kpi(c1, "Direct's share of cheap fares in December", u.fmt_pct(dec_actual),
      delta=f"{u.fmt_pp(dec_actual - dec_proj)} above trend", delta_color="normal",
      help="Direct's share was already trending up; December ran a little ahead of that trend.")
u.kpi(c2, "Cheap orders/month that vanished from Aeroprice", f"{displaced:,}",
      help="Summer vs last-quarter drop in Aeroprice cheap-fare orders — demand not recaptured elsewhere.")

st.divider()

# --- Chart: Direct share vs projected trend, gap shaded ----------------------
xs = [MN[mo - 1] for mo in ds["month"]]
fig = go.Figure()
fig.add_trace(go.Scatter(x=xs, y=ds["projected"], name="If the old trend had continued",
                         line=dict(color=u.COLORS["neutral"], width=2, dash="dash")))
fig.add_trace(go.Scatter(x=xs, y=ds["share_pct"], name="Direct's actual share",
                         line=dict(color=u.COLORS["less"], width=3), mode="lines+markers",
                         fill="tonexty", fillcolor="rgba(46,125,50,0.12)"))
fig.add_vline(x=8.5, line_dash="dot", line_color="#444",
              annotation_text="new fee starts", annotation_position="top left")
fig.update_yaxes(title_text="Direct's share of all cheap-fare orders, %")
u.chart(fig, "Since the fee change, Direct is winning a bigger slice of budget fares than its trend predicted")

st.divider()

# --- Interactive: win-back calculator ---------------------------------------
st.subheader("What winning those fares back on Direct is worth")
won = st.slider("Cheap-fare orders per month won back via Direct", 0, displaced,
                value=min(500, displaced), step=50)
saved = won * 12 * avg_cheap_fee
u.md(f"## :green[{u.fmt_usd(saved)} per year in avoided channel fees]")
u.caption(
    f"{won:,} orders/month × 12 months × ${avg_cheap_fee:,.2f} average partner fee on a cheap fare. "
    "That fee is money we keep when the sale happens on our own site instead."
)

st.divider()

# --- Closing recommendations ------------------------------------------------
st.subheader("What we recommend")
u.md(
    f"1. **Stop competing on sub-${u.BREAKEVEN:,.0f} fares inside Aeroprice** — after the new floor, "
    "they are structurally unprofitable there.\n\n"
    f"2. **Reinvest the ~${abs(u.load_zone_summary().set_index('zone_plain').loc['Pays less','avg_delta']):,.2f}/order "
    "saving on expensive fares** into sharper prices on long-haul, where we now win.\n\n"
    "3. **Make Direct the designated home for budget fares** — every captured order saves at least "
    f"${avg_cheap_fee:,.2f} in fees.\n\n"
    f"4. **Use the {u.fmt_usd(u.full_year_delta(), signed=True)} full-year number to renegotiate a tiered fee** "
    "that doesn't punish the cheap tickets that are most of our volume."
)
