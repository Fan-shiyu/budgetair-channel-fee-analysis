"""Page 1 — The Fee Change: old vs new fee by ticket price."""
import streamlit as st

import utils as u

u.page_setup("The Fee Change", "🔀")

u.header(
    "The fee change: cheap tickets pay more, expensive tickets pay less",
    f"**Below a ${u.BREAKEVEN:,.0f} ticket the new terms charge us more than the old ones; "
    "above it they charge less — and most of the channel sits below that line.**",
)

# --- Fee-curve line chart (shared builder in core.py) -----------------------
u.show(u.build_fee_curve_fig())

st.divider()

# --- Interactive: enter a ticket price --------------------------------------
st.subheader("Try a ticket price")
price = st.number_input("Enter a ticket price ($)", min_value=0.0, max_value=5000.0,
                        value=100.0, step=10.0)
old = float(u.fee_curve(price, **u.OLD_SCHEME))
new = float(u.fee_curve(price, **u.NEW_SCHEME))
diff = new - old

k1, k2 = st.columns(2)
u.kpi(k1, "Old fee", f"${old:,.2f}")
u.kpi(k2, "New fee", f"${new:,.2f}", delta=u.fmt_usd(diff, signed=True, cents=True),
      delta_color="inverse")

if diff > 0:
    u.md(f"### :red[This ticket pays {u.fmt_usd(diff, cents=True)} MORE under the new terms.]")
elif diff < 0:
    u.md(f"### :green[This ticket pays {u.fmt_usd(abs(diff), cents=True)} LESS under the new terms.]")
else:
    u.md("### The fee is the same under both schemes for this ticket.")
