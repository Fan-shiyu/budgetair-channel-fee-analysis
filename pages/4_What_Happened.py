"""Page 4 — What happened after October 1: the cheap fares left."""
import plotly.graph_objects as go
import streamlit as st

import utils as u

u.page_setup("What Happened", "📉")

MN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

ae_change = u.aeroprice_cheap_change() * 100
gf_change = u.cheap_volume_change(u.CONTROL_CHANNEL) * 100
share_pre = u.cheap_share_pooled(u.PRE_MONTHS) * 100
share_post = u.cheap_share_pooled(u.POST_MONTHS) * 100

u.header(
    "After the fee change, cheap fares didn't move channels — they disappeared",
    f"**Aeroprice cheap-ticket volume fell {u.fmt_pct(ae_change, signed=True)} while a comparable "
    f"channel with no fee change moved only {u.fmt_pct(gf_change, signed=True)}. The lost orders were "
    "mostly not picked up anywhere else — likely lost to competitors.**",
)

c1, c2, c3 = st.columns(3)
u.kpi(c1, "Aeroprice cheap-fare volume", u.fmt_pct(ae_change, signed=True),
      help="Summer (Jul–Sep) average vs last-quarter (Oct–Dec) average.")
u.kpi(c2, "Control channel (no fee change)", u.fmt_pct(gf_change, signed=True),
      help="Same comparison for a channel whose fee did not change.")
u.kpi(c3, "Aeroprice's share of cheap fares", u.fmt_pct(share_post),
      delta=f"{u.fmt_pp(share_post - share_pre)} · was {u.fmt_pct(share_pre)}",
      delta_color="normal",
      help="Pooled share of all cheap-fare orders: Aeroprice cheap orders / all cheap orders, "
           "Jan–Sep before the change vs Oct–Dec after.")

st.divider()

# --- Chart A: cheap-fare volume vs control (shared builder in core.py) -------
u.show(u.build_channel_trends_fig())
u.caption("Both lines are set to 100 at their July–September average so you can compare the drop, "
          "not the raw sizes.")

st.divider()

# --- Chart B: Aeroprice median ticket by month ------------------------------
aem = u.load_aeroprice_monthly().sort_values("month")
figb = go.Figure(go.Scatter(
    x=[MN[mo - 1] for mo in aem["month"]], y=aem["median_ticket"],
    line=dict(color=u.COLORS["brand"], width=3), mode="lines+markers",
))
figb.add_vline(x=8.5, line_dash="dot", line_color="#444",
               annotation_text="new fee starts", annotation_position="top left")
figb.update_yaxes(title_text="Middle (median) ticket price, $")
u.chart(figb, "Cheap tickets left the channel: the typical Aeroprice ticket jumped after October",
        height=400)
