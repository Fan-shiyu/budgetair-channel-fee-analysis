"""Page 4 — What happened after October 1: the cheap fares left."""
import plotly.graph_objects as go
import streamlit as st

import utils as u

u.page_setup("What Happened")

MN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

m = u.load_monthly_cheap_by_channel()
ae = m[m["Channel"] == u.CHANNEL].set_index("month")["orders"]
gf = m[m["Channel"] == u.CONTROL_CHANNEL].set_index("month")["orders"]
allc = m[m["Channel"] == "All channels"].set_index("month")["orders"]

ae_change = u.aeroprice_cheap_change() * 100
gf_change = u._cheap_change(u.CONTROL_CHANNEL) * 100
share_pre = (ae.reindex([7, 8, 9]).sum() / allc.reindex([7, 8, 9]).sum()) * 100
share_post = (ae.reindex([10, 11, 12]).sum() / allc.reindex([10, 11, 12]).sum()) * 100

st.title("After the fee change, cheap fares didn't move channels — they disappeared")
u.md(
    f"**Aeroprice cheap-ticket volume fell {u.fmt_pct(ae_change, signed=True)} while a comparable "
    f"channel with no fee change moved only {u.fmt_pct(gf_change, signed=True)}. The lost orders were "
    "mostly not picked up anywhere else — likely lost to competitors.**"
)

c1, c2, c3 = st.columns(3)
c1.metric("Aeroprice cheap-fare volume", u.fmt_pct(ae_change, signed=True),
          help="Summer (Jul–Sep) average vs last-quarter (Oct–Dec) average.")
c2.metric("Control channel (no fee change)", u.fmt_pct(gf_change, signed=True),
          help="Same comparison for a channel whose fee did not change.")
c3.metric("Aeroprice's share of cheap fares", u.fmt_pct(share_post),
          delta=f"was {u.fmt_pct(share_pre)} before", delta_color="off")

st.divider()

# --- Chart A: indexed cheap-fare volume, Aeroprice vs control ----------------
sep_ae, sep_gf = ae.loc[9], gf.loc[9]
months = list(range(1, 13))
fig = go.Figure()
fig.add_trace(go.Scatter(x=[MN[i - 1] for i in months], y=[ae.loc[i] / sep_ae * 100 for i in months],
                         name="Aeroprice (fee changed)", line=dict(color=u.COLORS["more"], width=3)))
fig.add_trace(go.Scatter(x=[MN[i - 1] for i in months], y=[gf.loc[i] / sep_gf * 100 for i in months],
                         name="Comparable channel (no fee change)",
                         line=dict(color=u.COLORS["neutral"], width=2, dash="dash")))
fig.add_vline(x=8.5, line_dash="dot", line_color="#444",
              annotation_text="new fee starts", annotation_position="top left")
fig.update_layout(
    title="Cheap-fare orders collapsed in Aeroprice but held steady where the fee didn't change",
    yaxis_title="Cheap-fare orders (September 2022 = 100)", template="simple_white",
    height=440, legend=dict(orientation="h", y=1.1), margin=dict(t=90),
)
st.plotly_chart(fig, use_container_width=True, config=u.PLOTLY_CONFIG)
u.caption("Both lines are set to 100 in September so you can compare the drop, not the raw sizes.")

st.divider()

# --- Chart B: Aeroprice median ticket by month ------------------------------
aem = u.load_aeroprice_monthly().sort_values("month")
figb = go.Figure(go.Scatter(
    x=[MN[m - 1] for m in aem["month"]], y=aem["median_ticket"],
    line=dict(color=u.COLORS["brand"], width=3), mode="lines+markers",
    text=[f"${v:,.0f}" for v in aem["median_ticket"]],
))
figb.add_vline(x=8.5, line_dash="dot", line_color="#444",
               annotation_text="new fee starts", annotation_position="top left")
figb.update_layout(
    title="Cheap tickets left the channel: the typical Aeroprice ticket jumped after October",
    yaxis_title="Middle (median) ticket price, $", template="simple_white",
    height=400, margin=dict(t=70),
)
st.plotly_chart(figb, use_container_width=True, config=u.PLOTLY_CONFIG)
