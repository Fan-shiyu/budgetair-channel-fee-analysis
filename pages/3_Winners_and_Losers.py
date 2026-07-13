"""Page 3 — Winners & Losers: who pays more and who pays less."""
import streamlit as st

import utils as u

u.page_setup("Winners & Losers", "⚖️")

zsum = u.load_zone_summary().set_index("zone_plain")
stats = u.load_stats()
cheap_avg = zsum.loc["Pays more", "avg_delta"]
exp_avg = zsum.loc["Pays less", "avg_delta"]
eff_old = stats["sub100_eff_old_pct"]
eff_new = stats["sub100_eff_new_pct"]

u.header(
    "The same change punishes budget airlines and rewards long-haul ones",
    f"**A cheap ticket now costs us {u.fmt_usd(cheap_avg, signed=True, cents=True)} more per order; an "
    f"expensive one saves {u.fmt_usd(abs(exp_avg), cents=True)}. On a sub-$100 ticket the effective fee "
    f"jumps from {u.fmt_pct(eff_old)} to {u.fmt_pct(eff_new)}.**",
)

c1, c2, c3 = st.columns(3)
u.kpi(c1, "Extra cost on a cheap fare", u.fmt_usd(cheap_avg, signed=True, cents=True))
u.kpi(c2, "Saving on an expensive fare", u.fmt_usd(exp_avg, signed=True, cents=True))
u.kpi(c3, "Effective fee on a sub-$100 ticket", u.fmt_pct(eff_new),
      delta=f"{u.fmt_pp(eff_new - eff_old)} vs old", delta_color="inverse",
      help="Total fee as a share of ticket value on tickets under $100 — old scheme vs new.")

st.divider()

# --- Interactive: pick a lens for the bar chart (shared builder in core.py) --
view = st.selectbox("View by:",
                    ["Airline", "Journey type", "Domestic vs International", "Ticket price zone"])
_DIM = {"Airline": "airline", "Journey type": "journey_type",
        "Domestic vs International": "domestic_international", "Ticket price zone": "ticket_zone"}
u.show(u.build_winners_losers_fig(_DIM[view]))

st.divider()

# --- Zone table -------------------------------------------------------------
st.subheader("The three price bands at a glance")
tbl = u.load_zone_summary()[["zone_plain", "orders", "share_pct", "avg_delta", "total_delta", "avg_margin"]].copy()
tbl.columns = ["", "Orders", "Share of channel", "Avg fee change / order",
               "Total fee change", "Avg margin / order"]
tbl["Share of channel"] = tbl["Share of channel"].map(u.fmt_pct)
tbl["Avg fee change / order"] = tbl["Avg fee change / order"].map(lambda v: u.fmt_usd(v, signed=True, cents=True))
tbl["Total fee change"] = tbl["Total fee change"].map(lambda v: u.fmt_usd(v, signed=True))
tbl["Avg margin / order"] = tbl["Avg margin / order"].map(lambda v: u.fmt_usd(v, signed=True, cents=True))
tbl["Orders"] = tbl["Orders"].map(lambda v: f"{v:,.0f}")
# st.table (static HTML) instead of st.dataframe (lazy canvas) so it always
# renders in screenshots; the zone label becomes the row header.
st.table(tbl.set_index(tbl.columns[0]))
u.caption(
    "The cheap band is 3 in 5 orders and already runs at about break-even, so the extra fee turns "
    "it loss-making. The expensive band, where we save, is under a third of orders."
)
