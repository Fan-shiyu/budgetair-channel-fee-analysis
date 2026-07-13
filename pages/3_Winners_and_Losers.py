"""Page 3 — Winners & Losers: who pays more and who pays less."""
import plotly.graph_objects as go
import streamlit as st

import utils as u

u.page_setup("Winners & Losers")

zsum = u.load_zone_summary().set_index("zone_plain")
stats = u.load_stats()
cheap_avg = zsum.loc["Pays more", "avg_delta"]
exp_avg = zsum.loc["Pays less", "avg_delta"]

st.title("The same change punishes budget airlines and rewards long-haul ones")
u.md(
    f"**A cheap ticket now costs us {u.fmt_usd(cheap_avg, signed=True)} more per order; an expensive "
    f"one saves {u.fmt_usd(abs(exp_avg))}. On a sub-$100 ticket the effective fee jumps from "
    f"{u.fmt_pct(stats['sub100_eff_old_pct'])} to {u.fmt_pct(stats['sub100_eff_new_pct'])}.**"
)

c1, c2, c3 = st.columns(3)
c1.metric("Extra cost on a cheap fare", u.fmt_usd(cheap_avg, signed=True))
c2.metric("Saving on an expensive fare", u.fmt_usd(exp_avg, signed=True))
c3.metric("Effective fee on a sub-$100 ticket",
          u.fmt_pct(stats["sub100_eff_new_pct"]),
          delta=f"was {u.fmt_pct(stats['sub100_eff_old_pct'])}", delta_color="inverse",
          help="Total fee as a share of ticket value on tickets under $100 — old scheme vs new.")

st.divider()

# --- Interactive: pick a lens for the bar chart -----------------------------
view = st.selectbox("View by:",
                    ["Airline", "Journey type", "Domestic vs International", "Ticket price zone"])

if view == "Airline":
    d = u.load_carrier_impact().rename(columns={"carrier": "category", "avg_delta": "value"})
    d = d[["category", "value"]]
else:
    dim = u.load_dimension_impact()
    d = dim[dim["dimension"] == view].rename(columns={"category": "category", "avg_delta": "value"})
    d = d[["category", "value"]]

d = d.sort_values("value")
colors = [u.COLORS["more"] if v > 0 else u.COLORS["less"] for v in d["value"]]

fig = go.Figure(go.Bar(
    x=d["value"], y=d["category"], orientation="h", marker_color=colors,
    text=[u.fmt_usd(v, signed=True) for v in d["value"]], textposition="outside",
))
fig.update_layout(
    title=f"Average change in fee per order, by {view.lower()} (red = pays more, green = pays less)",
    xaxis_title="Change in fee per order, $", template="simple_white",
    height=420 if view != "Airline" else 520, margin=dict(t=70, l=140),
)
st.plotly_chart(fig, use_container_width=True, config=u.PLOTLY_CONFIG)

st.divider()

# --- Zone table -------------------------------------------------------------
st.subheader("The three price bands at a glance")
tbl = u.load_zone_summary()[["zone_plain", "orders", "share_pct", "avg_delta", "total_delta", "avg_margin"]].copy()
tbl.columns = ["", "Orders", "Share of channel", "Avg fee change / order",
               "Total fee change", "Avg margin / order"]
tbl["Share of channel"] = tbl["Share of channel"].map(u.fmt_pct)
tbl["Avg fee change / order"] = tbl["Avg fee change / order"].map(lambda v: u.fmt_usd(v, signed=True))
tbl["Total fee change"] = tbl["Total fee change"].map(lambda v: u.fmt_usd(v, signed=True))
tbl["Avg margin / order"] = tbl["Avg margin / order"].map(lambda v: u.fmt_usd(v, signed=True))
tbl["Orders"] = tbl["Orders"].map(lambda v: f"{v:,.0f}")
st.dataframe(tbl, hide_index=True, use_container_width=True)
u.caption(
    "The cheap band is 3 in 5 orders and already runs at about break-even, so the extra fee turns "
    "it loss-making. The expensive band, where we save, is under a third of orders."
)
