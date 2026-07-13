"""Page 1 — The Fee Change: old vs new fee by ticket price."""
import numpy as np
import plotly.graph_objects as go
import streamlit as st

import utils as u

u.page_setup("The Fee Change")

st.title("The fee change: cheap tickets pay more, expensive tickets pay less")
u.md(
    f"**Below a ${u.BREAKEVEN:,.0f} ticket, the new terms charge us more than the old ones; "
    "above it, they charge less — and most of the channel sits below that line.**"
)

# --- Fee-curve line chart (curves generated from fee_curve, not hand points) -
tickets = np.linspace(0, 800, 400)
old_fee = u.fee_curve(tickets, **u.OLD_SCHEME)
new_fee = u.fee_curve(tickets, **u.NEW_SCHEME)

fig = go.Figure()
# shaded regions: red below break-even (pays more), green above (pays less)
fig.add_vrect(x0=0, x1=u.BREAKEVEN, fillcolor=u.COLORS["more"], opacity=0.08, line_width=0,
              annotation_text="pays MORE under new terms", annotation_position="top left")
fig.add_vrect(x0=u.BREAKEVEN, x1=800, fillcolor=u.COLORS["less"], opacity=0.08, line_width=0,
              annotation_text="pays LESS", annotation_position="top right")
fig.add_trace(go.Scatter(x=tickets, y=old_fee, name="Old fee (before Oct 2022)",
                         line=dict(color=u.COLORS["old"], dash="dash", width=2)))
fig.add_trace(go.Scatter(x=tickets, y=new_fee, name="New fee (from Oct 2022)",
                         line=dict(color=u.COLORS["new"], width=3)))
fig.add_vline(x=u.BREAKEVEN, line_dash="dot", line_color="#444",
              annotation_text=f"break-even ${u.BREAKEVEN:,.0f}", annotation_position="bottom right")
fig.update_layout(
    title=f"The new fee only saves money above a ${u.BREAKEVEN:,.0f} ticket",
    xaxis_title="Ticket price (base fare + tax), $",
    yaxis_title="Fee we pay per order, $",
    template="simple_white", height=460, legend=dict(orientation="h", y=1.08),
    margin=dict(t=90),
)
st.plotly_chart(fig, use_container_width=True, config=u.PLOTLY_CONFIG)

st.divider()

# --- Interactive: enter a ticket price --------------------------------------
st.subheader("Try a ticket price")
price = st.number_input("Enter a ticket price ($)", min_value=0.0, max_value=5000.0,
                        value=100.0, step=10.0)
old = float(u.fee_curve(price, **u.OLD_SCHEME))
new = float(u.fee_curve(price, **u.NEW_SCHEME))
diff = new - old

k1, k2 = st.columns(2)
k1.metric("Old fee", f"${old:,.2f}")
k2.metric("New fee", f"${new:,.2f}", delta=f"{u.fmt_usd(diff, signed=True)}",
          delta_color="inverse")

if diff > 0:
    u.md(f"### :red[This ticket pays {u.fmt_usd(diff)} MORE under the new terms.]")
elif diff < 0:
    u.md(f"### :green[This ticket pays {u.fmt_usd(abs(diff))} LESS under the new terms.]")
else:
    u.md("### The fee is the same under both schemes for this ticket.")
