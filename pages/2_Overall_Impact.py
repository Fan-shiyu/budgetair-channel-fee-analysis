"""Page 2 — Overall Impact: the full-year bill and where it comes from."""
import plotly.graph_objects as go
import streamlit as st

import utils as u

u.page_setup("Overall Impact")

st.title("The new fee would have cost us six figures on last year's orders")

pre = u.aeroprice_summary("pre")
full_delta = u.full_year_delta()
q4 = u.q4_delta()
pre_delta = pre["fee_delta"].sum()
pre_orders = pre["orders"].sum()
pre_margin = pre["total_margin"].sum()
avg_pre = pre_delta / pre_orders
pct_of_margin = pre_delta / pre_margin * 100

u.md(
    f"**Same orders, both price schemes: the new fee costs {u.fmt_usd(full_delta, signed=True)} "
    f"across the full year — the same as **{u.fmt_pct(pct_of_margin)}** of what we earned on the "
    "channel before the change.**"
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Full-year extra cost", u.fmt_usd(full_delta, signed=True))
c2.metric("If we only look after the change", u.fmt_usd(q4, signed=True),
          help="On Oct–Dec orders alone the new fee looks almost free — see the caption below the chart.")
c3.metric("Extra cost per order (Jan–Sep mix)", u.fmt_usd(avg_pre, signed=True))
c4.metric("As a share of channel earnings", u.fmt_pct(pct_of_margin),
          help="Full-year extra cost measured against Aeroprice margin earned Jan–Sep.")

st.divider()

# --- Chart A: waterfall, reacts to the period radio -------------------------
period_label = st.radio("Look at:", ["Full year", "After the change only"], horizontal=True)
period = "full" if period_label == "Full year" else "q4"
z = u.zone_deltas(period)

names = [f"Cheap tickets (<${u.BREAKEVEN:,.0f})", "Mid-price tickets",
         f"Expensive (>${u.CAP_MIN:,.0f})", "NET change"]
vals = [z.loc[u.ZONE_CHEAP, "total_delta"], z.loc[u.ZONE_MID, "total_delta"],
        z.loc[u.ZONE_CAP, "total_delta"], None]
net = z["total_delta"].sum()

fig = go.Figure(go.Waterfall(
    orientation="v",
    measure=["relative", "relative", "relative", "total"],
    x=names,
    y=[vals[0], vals[1], vals[2], net],
    text=[u.fmt_usd(v, signed=True) for v in [vals[0], vals[1], vals[2], net]],
    textposition="outside",
    connector=dict(line=dict(color="#bbb")),
    increasing=dict(marker=dict(color=u.COLORS["more"])),
    decreasing=dict(marker=dict(color=u.COLORS["less"])),
    totals=dict(marker=dict(color=u.COLORS["brand"])),
))
fig.update_layout(
    title=f"Cheap tickets drive the whole bill — {u.fmt_usd(net, signed=True)} ({period_label.lower()})",
    yaxis_title="Change in fees, $", template="simple_white", height=440, margin=dict(t=80),
)
st.plotly_chart(fig, use_container_width=True, config=u.PLOTLY_CONFIG)

u.caption(
    "Why the two views differ: after the change, the cheap tickets that get punished had already "
    "left the channel — so on the leftover mix the new fee looks almost free. On the mix we actually "
    "sold all year, it is expensive."
)

st.divider()

# --- Chart B: monthly total fee delta bars ----------------------------------
aem = u.load_aeroprice_monthly().sort_values("month")
month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
labels = [month_names[m - 1] for m in aem["month"]]
colors = [u.COLORS["more"] if d > 0 else u.COLORS["less"] for d in aem["fee_delta"]]

figb = go.Figure(go.Bar(x=labels, y=aem["fee_delta"], marker_color=colors,
                        text=[u.fmt_usd(v, signed=True) for v in aem["fee_delta"]],
                        textposition="outside"))
figb.add_vline(x=8.5, line_dash="dot", line_color="#444",
               annotation_text="new fee starts", annotation_position="top left")
figb.update_layout(
    title="The extra cost was building all year until cheap fares left in October",
    yaxis_title="Extra fee that month, $", template="simple_white", height=420, margin=dict(t=70),
)
st.plotly_chart(figb, use_container_width=True, config=u.PLOTLY_CONFIG)
