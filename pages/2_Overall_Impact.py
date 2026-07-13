"""Page 2 — Overall Impact: the full-year bill and where it comes from."""
import plotly.graph_objects as go
import streamlit as st

import utils as u

u.page_setup("Overall Impact", "💵")

pre = u.aeroprice_summary("pre")
full_delta = u.full_year_delta()
q4 = u.q4_delta()
pre_delta = pre["fee_delta"].sum()
avg_pre = pre_delta / pre["orders"].sum()
pct_of_margin = pre_delta / pre["total_margin"].sum() * 100

u.header(
    "The new fee would have cost us six figures on last year's orders",
    f"**Same orders, both price schemes: the new fee costs {u.fmt_usd(full_delta, signed=True)} "
    f"across the full year — as much as {u.fmt_pct(pct_of_margin)} of what we earned on the "
    "channel before the change.**",
)

c1, c2, c3, c4 = st.columns(4)
u.kpi(c1, "Full-year extra cost", u.fmt_usd(full_delta, signed=True))
u.kpi(c2, "If we only look after the change", u.fmt_usd(q4, signed=True),
      help="On Oct–Dec orders alone the new fee looks almost free — see the caption below the chart.")
u.kpi(c3, "Extra cost per order (Jan–Sep mix)", u.fmt_usd(avg_pre, signed=True, cents=True))
u.kpi(c4, "As a share of channel earnings", u.fmt_pct(pct_of_margin),
      help="Full-year extra cost measured against Aeroprice margin earned Jan–Sep.")

st.divider()

# --- Chart A: waterfall, reacts to the period radio -------------------------
period_label = st.radio("Look at:", ["Full year", "After the change only"], horizontal=True)
period = "full" if period_label == "Full year" else "q4"
z = u.zone_deltas(period)

names = [f"Cheap tickets (<${u.BREAKEVEN:,.0f})", "Mid-price tickets",
         f"Expensive (>${u.CAP_MIN:,.0f})", "NET change"]
vals = [z.loc[u.ZONE_CHEAP, "total_delta"], z.loc[u.ZONE_MID, "total_delta"],
        z.loc[u.ZONE_CAP, "total_delta"]]
net = z["total_delta"].sum()

figa = go.Figure(go.Waterfall(
    orientation="v",
    measure=["relative", "relative", "relative", "total"],
    x=names,
    y=vals + [net],
    text=[u.fmt_usd(v, signed=True) for v in vals + [net]],
    textposition="outside",
    connector=dict(line=dict(color="#cbd5e1")),
    increasing=dict(marker=dict(color=u.COLORS["more"])),
    decreasing=dict(marker=dict(color=u.COLORS["less"])),
    totals=dict(marker=dict(color=u.COLORS["brand"])),
))
figa.update_yaxes(title_text="Change in fees, $")
u.chart(figa, f"Cheap tickets drive the whole bill — {u.fmt_usd(net, signed=True)} ({period_label.lower()})")

u.caption(
    "Why the two views differ: after the change, the cheap tickets that get punished had already "
    "left the channel — so on the leftover mix the new fee looks almost free. On the mix we actually "
    "sold all year, it is expensive."
)

st.divider()

# --- Chart B: monthly total fee delta bars (shared builder in core.py) -------
u.show(u.build_monthly_delta_fig())
