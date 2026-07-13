"""Page 4 — What happened after October 1: the cheap fares left."""
import plotly.graph_objects as go
import streamlit as st

import utils as u

u.page_setup("What Happened", "📉")

MN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

m = u.load_monthly_cheap_by_channel()
ae = m[m["Channel"] == u.CHANNEL].set_index("month")["orders"]
gf = m[m["Channel"] == u.CONTROL_CHANNEL].set_index("month")["orders"]

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

# --- Chart A: cheap-fare volume, indexed to each channel's Jul-Sep AVERAGE ---
base_ae = ae.reindex(u.SUMMER_MONTHS).mean()
base_gf = gf.reindex(u.SUMMER_MONTHS).mean()
months = list(range(6, 13))   # start the x-axis at June
fig = go.Figure()
fig.add_trace(go.Scatter(x=[MN[i - 1] for i in months], y=[ae.loc[i] / base_ae * 100 for i in months],
                         name="Aeroprice (fee changed)", line=dict(color=u.COLORS["more"], width=3),
                         mode="lines+markers"))
fig.add_trace(go.Scatter(x=[MN[i - 1] for i in months], y=[gf.loc[i] / base_gf * 100 for i in months],
                         name="Comparable channel (no fee change)",
                         line=dict(color=u.COLORS["neutral"], width=2, dash="dash"),
                         mode="lines+markers"))
fig.add_vline(x=3.5, line_dash="dot", line_color="#444",
              annotation_text="new fee starts", annotation_position="top left")
fig.update_yaxes(title_text="Cheap-fare orders (Jul–Sep average = 100)")
u.chart(fig, "Cheap-fare orders collapsed in Aeroprice but held steady where the fee didn't change")
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
