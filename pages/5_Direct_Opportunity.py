"""Page 5 — The Direct opportunity: winning budget fares back on our own site."""
import numpy as np
import plotly.graph_objects as go
import streamlit as st

import utils as u

u.page_setup("Direct Opportunity")

MN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

ds = u.load_direct_share().sort_values("month")
# fit a straight-line trend on the pre-change months (1-9) and project 10-12
pre = ds[ds["month"] <= 9]
slope, intercept = np.polyfit(pre["month"], pre["share_pct"], 1)
ds["projected"] = slope * ds["month"] + intercept
dec_actual = ds.set_index("month").loc[12, "share_pct"]
dec_proj = ds.set_index("month").loc[12, "projected"]

# displaced cheap-fare orders / month not recaptured = Aeroprice's monthly cheap-fare loss
m = u.load_monthly_cheap_by_channel()
ae = m[m["Channel"] == u.CHANNEL].set_index("month")["orders"]
displaced = int(round(ae.reindex([7, 8, 9]).mean() - ae.reindex([10, 11, 12]).mean()))
avg_cheap_fee = u.load_stats()["avg_cheap_fee_new"]

st.title("Our own Direct site is the cheapest place to sell a budget fare")
u.md(
    f"**Cheap fares are already drifting to Direct — by December it reached "
    f"{u.fmt_pct(dec_actual)} of cheap-fare orders, ahead of its {u.fmt_pct(dec_proj)} trend. "
    f"Every budget order we win back there avoids at least ${avg_cheap_fee:,.2f} in partner fees.**"
)

c1, c2 = st.columns(2)
c1.metric("Direct's share of cheap fares in December", u.fmt_pct(dec_actual),
          delta=f"{u.fmt_pct(dec_actual - dec_proj, signed=True)} vs its own trend",
          help="Direct's share was already trending up; December ran a little ahead of that trend.")
c2.metric("Cheap orders/month that vanished from Aeroprice", f"{displaced:,}",
          help="Summer vs last-quarter drop in Aeroprice cheap-fare orders — demand not recaptured elsewhere.")

st.divider()

# --- Chart: Direct share vs projected trend, gap shaded ----------------------
xs = [MN[mo - 1] for mo in ds["month"]]
fig = go.Figure()
fig.add_trace(go.Scatter(x=xs, y=ds["projected"], name="If the old trend had continued",
                         line=dict(color=u.COLORS["neutral"], width=2, dash="dash")))
fig.add_trace(go.Scatter(x=xs, y=ds["share_pct"], name="Direct's actual share",
                         line=dict(color=u.COLORS["less"], width=3), fill="tonexty",
                         fillcolor="rgba(46,125,50,0.12)"))
fig.add_vline(x=8.5, line_dash="dot", line_color="#444",
              annotation_text="new fee starts", annotation_position="top left")
fig.update_layout(
    title="Since the fee change, Direct is winning a bigger slice of budget fares than its trend predicted",
    yaxis_title="Direct's share of all cheap-fare orders, %", template="simple_white",
    height=440, legend=dict(orientation="h", y=1.1), margin=dict(t=90),
)
st.plotly_chart(fig, use_container_width=True, config=u.PLOTLY_CONFIG)

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
    f"2. **Reinvest the ~${abs(u.load_zone_summary().set_index('zone_plain').loc['Pays less','avg_delta']):,.0f}/order "
    "saving on expensive fares** into sharper prices on long-haul, where we now win.\n\n"
    "3. **Make Direct the designated home for budget fares** — every captured order saves at least "
    f"${avg_cheap_fee:,.2f} in fees.\n\n"
    f"4. **Use the {u.fmt_usd(u.full_year_delta(), signed=True)} full-year number to renegotiate a tiered fee** "
    "that doesn't punish the cheap tickets that are most of our volume."
)
