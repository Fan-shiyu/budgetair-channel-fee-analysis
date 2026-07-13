"""The nine MCP tools. Each is a pure function returning an Envelope (no FastMCP
decorators here, so they are directly unit-testable). Every number is computed from
`core` / the parquet in `data`; the only literals are the fee-contract constants.
"""
import numpy as np
import pandas as pd

import core
from mcp_server import data
from mcp_server.envelope import Envelope, error_envelope

U = core.fmt_usd
P = core.fmt_pct
PP = core.fmt_pp


def _meta(**kw):
    kw.setdefault("data_version", data.data_version())
    return kw


def _aeroprice_orders():
    return int(core.load_zone_summary()["orders"].sum())


# --------------------------------------------------------------------------- #
# 1. get_overview
# --------------------------------------------------------------------------- #
def get_overview() -> Envelope:
    fy = core.full_year_delta()
    q4 = core.q4_delta()
    cheap_share = core.load_zone_summary().set_index("zone_plain").loc["Pays more", "share_pct"]
    ae_ch = core.aeroprice_cheap_change() * 100
    ctrl_ch = core.cheap_volume_change(core.CONTROL_CHANNEL) * 100
    pre_share = core.cheap_share_pooled(core.PRE_MONTHS) * 100
    post_share = core.cheap_share_pooled(core.POST_MONTHS) * 100
    floor = core.NEW_SCHEME["floor"]

    data_tbl = pd.DataFrame([
        ["Extra cost, full year (same orders, both schemes)", U(fy, signed=True)],
        ["On the after-change mix only", U(q4, signed=True)],
        ["Orders that pay more under the new terms", P(cheap_share)],
        ["Cheap-fare volume, Aeroprice vs control channel", f"{P(ae_ch, signed=True)} vs {P(ctrl_ch, signed=True)}"],
        ["Aeroprice share of cheap fares, before → after", f"{P(pre_share)} → {P(post_share)}"],
        ["Minimum fee saved per cheap order moved to Direct", U(floor, cents=True)],
    ], columns=["Metric", "Value"])

    facts = [
        f"The new contract looks cheaper (lower percentage, lower cap) but its brand-new "
        f"{U(floor, cents=True)} minimum fee lands on {P(cheap_share)} of Aeroprice orders — cheap "
        "tickets that were already barely profitable.",
        f"On the sales mix we actually had, the new fee costs {U(fy, signed=True)} a year; on the "
        f"after-change mix it looks roughly neutral ({U(q4, signed=True)}) — only because the punished "
        "cheap-fare segment had already left.",
        f"Cheap-fare volume collapsed in Aeroprice ({P(ae_ch, signed=True)}) while a comparable channel "
        f"with no fee change barely moved ({P(ctrl_ch, signed=True)}); most of that demand was not "
        "recaptured by our other channels.",
        f"Aeroprice's pooled share of all cheap-fare orders fell from {P(pre_share)} to {P(post_share)}; "
        f"the plan is to stop full-price competition on sub-{U(core.BREAKEVEN)} fares there, move budget "
        f"fares to our own Direct site (each saves at least {U(floor, cents=True)} in fees), and use the "
        f"{U(fy, signed=True)} number to renegotiate a tiered fee.",
    ]
    return Envelope(
        headline=f"On our 2022 orders the 'cheaper' new Aeroprice fee would have cost {U(fy, signed=True)} "
                 f"more — because a new {U(floor, cents=True)} minimum fee hit the cheap tickets that are "
                 "most of the channel.",
        data=data_tbl, facts=facts,
        meta=_meta(period="full year (all 2022)", n_orders=_aeroprice_orders(),
                   definitions="counterfactual = same orders, both fee schemes"),
        fig=core.build_fee_curve_fig(),
        values={"full_year_delta": float(fy), "q4_delta": float(q4),
                "cheap_share": float(cheap_share), "ae_change": float(ae_ch),
                "ctrl_change": float(ctrl_ch)},
    )


# --------------------------------------------------------------------------- #
# 2. get_fee_impact(period)
# --------------------------------------------------------------------------- #
def get_fee_impact(period="full_year") -> Envelope:
    try:
        months, label, _ = data.resolve_period(period)
    except ValueError as e:
        return error_envelope(str(e), valid_options=data.VALID_PERIODS, meta=_meta())

    ae = core.aeroprice_summary("full")
    sel = ae[ae["month"].isin(months)]
    orders = int(sel["orders"].sum())
    if orders == 0:
        return error_envelope(f"No Aeroprice orders in {label}.", meta=_meta(period=label))
    old = sel["fee_old_scheme"].sum()
    new = sel["fee_new_scheme"].sum()
    delta = sel["fee_delta"].sum()
    margin = sel["total_margin"].sum()
    per_order = delta / orders
    pct_vs_old = delta / old * 100 if old else 0.0
    pct_of_margin = delta / margin * 100 if margin else float("nan")

    is_full = set(months) == set(range(1, 13))
    q4_note = ""
    if is_full:
        q4v = core.q4_delta()
        q4_note = f" — though on the after-change mix alone (Oct–Dec) it is only {U(q4v, signed=True)}, roughly neutral"
    direction = "more expensive" if delta > 0 else ("cheaper" if delta < 0 else "neutral")
    data_tbl = pd.DataFrame([
        ["Old fee (4% / $24 cap)", U(old)],
        ["New fee (3.8% / $10.50 floor / $19 cap)", U(new)],
        ["Change (new − old)", U(delta, signed=True)],
        ["Change per order", U(per_order, signed=True, cents=True)],
        ["Change vs old fee", P(pct_vs_old, signed=True)],
        ["Change as share of margin", P(pct_of_margin, signed=True) if margin else "n/a"],
        ["Orders", f"{orders:,}"],
    ], columns=["Measure", "Value"])

    facts = [
        f"In {label}, the new fee is {U(delta, signed=True)} vs the old one across {orders:,} Aeroprice "
        f"orders — {P(pct_vs_old, signed=True)} on the old fee bill, or {U(per_order, signed=True, cents=True)} per order.",
        f"That is the counterfactual: both schemes applied to the same orders, so it is {direction} purely "
        "because of the contract, not seasonality or mix.",
    ]
    if margin:
        facts.append(f"Measured against the {U(margin)} of Aeroprice margin earned in {label}, the change "
                     f"is {P(pct_of_margin, signed=True)} of margin.")
    if is_full:
        facts.append(f"On the after-change mix alone (Oct–Dec) the same fee is only {U(core.q4_delta(), signed=True)} — "
                     "roughly neutral — because the punished cheap fares had already left the channel; on "
                     "the full-year mix we actually sold, it is expensive.")
    caveats = []
    if margin is not None and margin < 0:
        caveats.append("This period's Aeroprice margin is negative, so the 'share of margin' figure is "
                       "not meaningful — read the dollar change instead.")

    if is_full:
        head = (f"Full year: the new fee would have cost {U(delta, signed=True)} "
                f"({P(pct_vs_old, signed=True)}) more — but only {U(core.q4_delta(), signed=True)} on the "
                f"after-change mix alone (roughly neutral) — across {orders:,} Aeroprice orders.")
    else:
        head = (f"In {label}, switching to the new fee would have been {U(delta, signed=True)} "
                f"({P(pct_vs_old, signed=True)}) across {orders:,} Aeroprice orders.")
    return Envelope(
        headline=head,
        data=data_tbl, facts=facts, caveats=caveats,
        meta=_meta(period=label, n_orders=orders,
                   definitions="counterfactual = same orders, both fee schemes"),
        fig=core.build_monthly_delta_fig(highlight_months=months),
        values={"delta": float(delta), "old": float(old), "new": float(new),
                "per_order": float(per_order), "orders": orders},
    )


# --------------------------------------------------------------------------- #
# 3. fee_for_ticket(ticket_price)
# --------------------------------------------------------------------------- #
_RULE_TEXT = {"floor": "the $10.50 minimum", "percent": "the percentage rate",
              "cap": "the cap", }


def fee_for_ticket(ticket_price) -> Envelope:
    try:
        t = float(ticket_price)
    except (TypeError, ValueError):
        return error_envelope("ticket_price must be a number between 1 and 20,000.",
                              valid_options=["1 … 20000"], meta=_meta())
    if not (1 <= t <= 20000):
        return error_envelope(f"ticket_price {t:g} is out of range — enter a value between 1 and 20,000.",
                              valid_options=["1 … 20000"], meta=_meta())

    old = float(core.fee_curve(t, **core.OLD_SCHEME))
    new = float(core.fee_curve(t, **core.NEW_SCHEME))
    diff = new - old
    rule_old = core.binding_rule(t, core.OLD_SCHEME)
    rule_new = core.binding_rule(t, core.NEW_SCHEME)
    verdict = ("pays " + U(diff, cents=True) + " MORE" if diff > 0
               else "pays " + U(abs(diff), cents=True) + " LESS" if diff < 0
               else "pays the same")

    data_tbl = pd.DataFrame([
        ["Old scheme", U(old, cents=True), _RULE_TEXT[rule_old]],
        ["New scheme", U(new, cents=True), _RULE_TEXT[rule_new]],
        ["Difference", U(diff, signed=True, cents=True), "new − old"],
    ], columns=["Scheme", "Fee", "Set by"])

    facts = [
        f"A ${t:,.0f} ticket {verdict} under the new terms: {U(old, cents=True)} old vs {U(new, cents=True)} new.",
        f"Old fee is set by {_RULE_TEXT[rule_old]}; new fee is set by {_RULE_TEXT[rule_new]}.",
    ]
    if t < core.BREAKEVEN:
        facts.append(f"It sits below the ${core.BREAKEVEN:,.2f} break-even, where the new $10.50 minimum "
                     "beats the old 4% rate, so it costs more now.")
    return Envelope(
        headline=f"A ${t:,.0f} ticket {verdict} under the new fee ({U(old, cents=True)} → {U(new, cents=True)}).",
        data=data_tbl, facts=facts,
        meta=_meta(period="fee schedule (contract terms)",
                   definitions=f"break-even ${core.BREAKEVEN:,.2f} = $10.50 ÷ 4%"),
        fig=core.build_fee_curve_fig(mark_ticket=t if t <= 800 else None),
        values={"old": old, "new": new, "diff": diff, "rule_old": rule_old, "rule_new": rule_new},
    )


# --------------------------------------------------------------------------- #
# 4. winners_losers(dimension)
# --------------------------------------------------------------------------- #
def winners_losers(dimension="airline") -> Envelope:
    if dimension not in core._DIM_MAP:
        return error_envelope(f"Invalid dimension '{dimension}'.",
                              valid_options=data.DIMENSIONS, meta=_meta())
    d = core.winners_losers_table(dimension).copy()   # sorted desc by avg delta
    if dimension == "ticket_zone":
        # add the price ranges so 'expensive/cheap' map to the right row unambiguously
        zone_price = {"Pays more": "Cheap tickets <$262.50 (pay more)",
                      "About even": "Mid-price $262.50–500 (about even)",
                      "Pays less": "Expensive/long-haul >$500 (pay less)"}
        d["category"] = d["category"].map(lambda c: zone_price.get(c, c))
    loser, winner = d.iloc[0], d.iloc[-1]
    top = d.head(10)
    data_tbl = pd.DataFrame({
        "Segment": top["category"].astype(str).tolist(),
        "Avg fee change / order": [U(v, signed=True, cents=True) for v in top["value"]],
        "Orders": [f"{int(n):,}" for n in top["orders"]],
        "Total fee change": [U(v, signed=True) for v in top["total_delta"]],
    })
    label = core._DIM_MAP[dimension][1]
    top3 = d.head(3)
    facts = [
        "Hardest hit by " + label + ": "
        + ", ".join(f"{r['category']} ({U(r['value'], signed=True, cents=True)}/order)"
                    for _, r in top3.iterrows()) + ".",
        f"Biggest loser: {loser['category']} at {U(loser['value'], signed=True, cents=True)} per order "
        f"across {int(loser['orders']):,} orders ({U(loser['total_delta'], signed=True)} total).",
        f"Biggest winner: {winner['category']} at {U(winner['value'], signed=True, cents=True)} per order "
        f"across {int(winner['orders']):,} orders ({U(winner['total_delta'], signed=True)} total).",
        "Red = pays more under the new fee, green = pays less; the ranking is by average change per order.",
    ]
    return Envelope(
        headline=f"By {label}, the hardest hit is {loser['category']} "
                 f"({U(loser['value'], signed=True, cents=True)}/order) and the biggest winner is "
                 f"{winner['category']} ({U(winner['value'], signed=True, cents=True)}/order).",
        data=data_tbl, facts=facts,
        meta=_meta(period="full year (all 2022)", n_orders=int(d["orders"].sum()),
                   definitions="avg change per order = total fee delta ÷ orders in the segment"),
        fig=core.build_winners_losers_fig(dimension),
        values={"loser": loser["category"], "loser_avg": float(loser["value"]),
                "winner": winner["category"], "winner_avg": float(winner["value"])},
    )


# --------------------------------------------------------------------------- #
# 5. channel_trends
# --------------------------------------------------------------------------- #
def channel_trends() -> Envelope:
    ae_ch = core.aeroprice_cheap_change() * 100
    ctrl_ch = core.cheap_volume_change(core.CONTROL_CHANNEL) * 100
    pre_share = core.cheap_share_pooled(core.PRE_MONTHS) * 100
    post_share = core.cheap_share_pooled(core.POST_MONTHS) * 100
    total_pre = core.total_cheap_monthly(core.SUMMER_MONTHS)
    total_post = core.total_cheap_monthly(core.POST_MONTHS)

    def summer_post(ch):
        s = core._monthly_cheap(ch)
        return s.reindex(core.SUMMER_MONTHS).mean(), s.reindex(core.POST_MONTHS).mean()

    ae_s, ae_p = summer_post(core.CHANNEL)
    gf_s, gf_p = summer_post(core.CONTROL_CHANNEL)
    data_tbl = pd.DataFrame([
        ["Aeroprice (fee changed)", f"{ae_s:,.0f}", f"{ae_p:,.0f}", P(ae_ch, signed=True)],
        [f"{core.CONTROL_CHANNEL} (no fee change)", f"{gf_s:,.0f}", f"{gf_p:,.0f}", P(ctrl_ch, signed=True)],
        ["All channels", f"{total_pre:,.0f}", f"{total_post:,.0f}",
         P((total_post - total_pre) / total_pre * 100, signed=True)],
    ], columns=["Channel", "Jul–Sep avg / mo", "Oct–Dec avg / mo", "Change"])

    facts = [
        f"Aeroprice cheap-fare volume fell {P(ae_ch, signed=True)} from its summer average to the last "
        f"quarter, while a comparable channel with no fee change moved only {P(ctrl_ch, signed=True)} — so "
        "the drop is the fee, not the season.",
        f"Aeroprice's pooled share of all cheap-fare orders fell from {P(pre_share)} to {P(post_share)}.",
        f"Total cheap-fare orders across all channels fell from about {total_pre:,.0f} to {total_post:,.0f} "
        "per month, so most of the displaced demand was not recaptured anywhere — it was likely lost to competitors.",
    ]
    ae_monthly = core._monthly_cheap(core.CHANNEL)
    low_m, low_v = int(ae_monthly.idxmin()), int(ae_monthly.min())
    peak_m, peak_v = int(ae_monthly.idxmax()), int(ae_monthly.max())
    facts.append(
        f"Aeroprice cheap-fare volume peaked in {core.MONTH_NAMES[peak_m - 1]} (~{peak_v:,} orders) and was "
        f"worst — its lowest — in {core.MONTH_NAMES[low_m - 1]} (~{low_v:,} orders), after the fee drove cheap "
        "fares out of the channel.")
    return Envelope(
        headline=f"After the change, Aeroprice cheap-fare volume fell {P(ae_ch, signed=True)} vs "
                 f"{P(ctrl_ch, signed=True)} on a no-fee-change channel — the demand mostly disappeared, not moved.",
        data=data_tbl, facts=facts,
        meta=_meta(period="Jul–Sep vs Oct–Dec 2022",
                   definitions="cheap fare = ticket < $262.50; indexed to Jul–Sep average"),
        fig=core.build_channel_trends_fig(),
        values={"ae_change": float(ae_ch), "ctrl_change": float(ctrl_ch),
                "pre_share": float(pre_share), "post_share": float(post_share),
                "total_pre": float(total_pre), "total_post": float(total_post)},
    )


# --------------------------------------------------------------------------- #
# 6. direct_opportunity(orders_per_month?)
# --------------------------------------------------------------------------- #
def direct_opportunity(orders_per_month=0) -> Envelope:
    try:
        n = int(orders_per_month)
    except (TypeError, ValueError):
        return error_envelope("orders_per_month must be a whole number between 0 and 2,200.",
                              valid_options=["0 … 2200"], meta=_meta())
    if not (0 <= n <= 2200):
        return error_envelope(f"orders_per_month {n} is out of range (0 … 2,200).",
                              valid_options=["0 … 2200"], meta=_meta())

    _, dec_actual, dec_proj = core.direct_trend()
    gap = dec_actual - dec_proj
    avg_fee = core.load_stats()["avg_cheap_fee_new"]

    facts = [
        f"By December, Direct handled {P(dec_actual)} of all cheap-fare orders, ahead of its own Jan–Sep "
        f"trend projection of {P(dec_proj)} — {PP(gap)} above trend.",
        f"Every cheap order sold on our own Direct site avoids at least {U(avg_fee, cents=True)}, the average "
        "new-scheme Aeroprice fee on a cheap fare.",
    ]
    rows = [["Direct share of cheap fares, December", P(dec_actual)],
            ["Its Jan–Sep trend projection", P(dec_proj)],
            ["Above trend", PP(gap)],
            ["Avg fee avoided per cheap order won back", U(avg_fee, cents=True)]]
    values = {"dec_actual": float(dec_actual), "dec_proj": float(dec_proj),
              "gap_pp": float(gap), "avg_fee": float(avg_fee), "orders_per_month": n}
    if n > 0:
        savings = n * 12 * avg_fee
        values["savings"] = float(savings)
        rows.append([f"If {n:,} cheap orders/month move to Direct", f"{U(savings)} / year saved"])
        facts.append(f"Winning back {n:,} cheap orders a month would save {U(savings)} a year in avoided "
                     f"channel fees ({n:,} × 12 × {U(avg_fee, cents=True)}).")
        headline = (f"Winning back {n:,} cheap orders/month via Direct saves about {U(savings)} a year in "
                    "avoided Aeroprice fees.")
    else:
        headline = (f"Direct already reached {P(dec_actual)} of cheap fares by December ({PP(gap)} above "
                    f"trend); each order won back there avoids at least {U(avg_fee, cents=True)} in fees.")

    return Envelope(
        headline=headline, data=pd.DataFrame(rows, columns=["Measure", "Value"]), facts=facts,
        meta=_meta(period="2022 (trend fit Jan–Sep)",
                   definitions="savings = orders × 12 × avg new-scheme Aeroprice fee on a cheap fare"),
        fig=core.build_direct_share_fig(), values=values,
    )


# --------------------------------------------------------------------------- #
# 7. segment_detail(...)
# --------------------------------------------------------------------------- #
def segment_detail(channel=None, period=None, ticket_zone=None, carrier=None,
                   journey_type=None, domestic_international=None) -> Envelope:
    echo = {}
    # --- resolve + validate every filter -----------------------------------
    try:
        ch = data.resolve_enum(channel, data.CHANNELS, "channel") if channel else None
        zone_plain = data.resolve_enum(ticket_zone, data.ZONES_PLAIN, "ticket_zone") if ticket_zone else None
        jt = data.resolve_enum(journey_type, data.JOURNEY_TYPES, "journey_type") if journey_type else None
        di = data.resolve_enum(domestic_international, data.DOMESTIC_INTL, "domestic_international") \
            if domestic_international else None
    except ValueError as e:
        return error_envelope(str(e), meta=_meta())

    months = label = None
    spans = False
    if period:
        try:
            months, label, spans = data.resolve_period(period)
        except ValueError as e:
            return error_envelope(str(e), valid_options=data.VALID_PERIODS, meta=_meta())

    car_code = car_name = None
    if carrier:
        car_code, car_name, suggestions = data.resolve_carrier(carrier)
        if car_code is None:
            msg = f"Carrier '{carrier}' not found."
            opts = suggestions if suggestions else [r["airline"] for r in data.carrier_catalog(10)[0]]
            return error_envelope(msg + " Try a valid carrier code or name.", valid_options=opts, meta=_meta())

    # --- build the slice ----------------------------------------------------
    df = data.SEGMENTS_NZ
    ref = df[df["Channel"] == ch] if ch else df          # benchmark reference set
    slc = ref
    if zone_plain:
        zkey = {v: k for k, v in core.ZONE_PLAIN.items()}[zone_plain]
        slc = slc[slc["ticket_zone"] == zkey]
    if jt:
        slc = slc[slc["Journey Type"] == jt]
    if di:
        slc = slc[slc["is_international"] == (di == "International")]
    if car_code:
        slc = slc[slc["Fare Carrier"] == car_code]
    if months:
        slc = slc[slc["month"].isin(months)]

    echo = {"channel": ch or "all channels", "period": label or "full year (all 2022)",
            "ticket_zone": zone_plain or "all zones", "carrier": (f"{car_name} ({car_code})" if car_code else "all carriers"),
            "journey_type": jt or "all", "domestic_international": di or "all"}
    n = int(len(slc))

    # --- empty -> an answer, not an error ----------------------------------
    if n == 0:
        facts = ["No orders match all of those filters at once. Try relaxing one — for example drop the "
                 "carrier or widen the period.",
                 "Valid channels: " + ", ".join(data.CHANNELS) + ".",
                 "Valid zones: " + ", ".join(data.ZONES_PLAIN) + "; journey types: "
                 + ", ".join(data.JOURNEY_TYPES) + "; periods: full_year, before_change, after_change, 2022-01…2022-12."]
        return Envelope(headline="No orders match that combination of filters.",
                        facts=facts, meta=_meta(filters=echo, n_orders=0), is_error=False)

    # --- volume block (with channel-average benchmark) ---------------------
    def block(frame):
        return {
            "orders": int(len(frame)),
            "passengers": int(frame["Number of Passengers"].sum()),
            "median_ticket": float(frame["total_ticket_value"].median()),
            "total_ticket": float(frame["total_ticket_value"].sum()),
            "avg_margin": float(frame["Margin"].mean()),
            "total_margin": float(frame["Margin"].sum()),
        }
    s, rb = block(slc), block(ref)
    share = s["orders"] / rb["orders"] * 100
    ref_name = ch or "all channels"

    rows = [
        ["Orders", f"{s['orders']:,}", f"{rb['orders']:,}"],
        ["Passengers", f"{s['passengers']:,}", f"{rb['passengers']:,}"],
        ["Share of " + ref_name, P(share), "100.0%"],
        ["Median ticket", U(s["median_ticket"], cents=True), U(rb["median_ticket"], cents=True)],
        ["Avg margin / order", U(s["avg_margin"], signed=True, cents=True), U(rb["avg_margin"], signed=True, cents=True)],
        ["Total margin", U(s["total_margin"], signed=True), U(rb["total_margin"], signed=True)],
    ]
    values = {"n": n, "share": float(share), **{f"slice_{k}": v for k, v in s.items()}}
    facts = [f"This slice is {s['orders']:,} orders ({P(share)} of {ref_name}), median ticket "
             f"{U(s['median_ticket'], cents=True)}, average margin {U(s['avg_margin'], signed=True, cents=True)}/order."]

    # --- fee block: only where fees exist (Aeroprice orders in the slice) ----
    # Fees are populated only for Aeroprice; show the block for the Aeroprice
    # portion of the slice, benchmarked against the Aeroprice channel average.
    ae_slice = slc if ch == core.CHANNEL else slc[slc["Channel"] == core.CHANNEL]
    ref_ae = (ref if ch == core.CHANNEL
              else data.SEGMENTS_NZ[data.SEGMENTS_NZ["Channel"] == core.CHANNEL])
    fee_shown = False
    if len(ae_slice) > 0 and (ch is None or ch == core.CHANNEL):
        fee_shown = True
        n_ae = int(len(ae_slice))
        d_tot = ae_slice["fee_delta"].sum()
        d_po = d_tot / n_ae
        ref_po = ref_ae["fee_delta"].sum() / len(ref_ae)
        eff_old = ae_slice["fee_old_scheme"].sum() / ae_slice["total_ticket_value"].sum() * 100
        eff_new = ae_slice["fee_new_scheme"].sum() / ae_slice["total_ticket_value"].sum() * 100
        raw = ae_slice["total_ticket_value"] * core.NEW_SCHEME["rate"]
        comp_floor = (raw <= core.NEW_SCHEME["floor"]).mean() * 100
        comp_cap = (raw >= core.NEW_SCHEME["cap"]).mean() * 100
        comp_lin = 100 - comp_floor - comp_cap
        mult = d_po / ref_po if ref_po else float("nan")
        suffix = "" if ch == core.CHANNEL else " (Aeroprice)"
        rows += [
            ["Fee change / order", U(d_po, signed=True, cents=True),
             U(ref_po, signed=True, cents=True) + suffix],
            ["Total fee change", U(d_tot, signed=True), ""],
            ["Effective fee rate (old → new)", f"{P(eff_old)} → {P(eff_new)}", ""],
            ["Floor / percent / cap mix", f"{P(comp_floor)} / {P(comp_lin)} / {P(comp_cap)}", ""],
        ]
        values.update({"fee_delta_total": float(d_tot), "fee_delta_per_order": float(d_po),
                       "benchmark_per_order": float(ref_po), "n_aeroprice": n_ae})
        scope = "" if ch == core.CHANNEL else f" (the {n_ae:,} Aeroprice orders in this slice)"
        mult_txt = f" — {mult:.1f}x the Aeroprice average hit." if mult == mult and mult > 0 else "."
        facts.append(f"Fee impact{scope}: {U(d_po, signed=True, cents=True)}/order vs "
                     f"{U(ref_po, signed=True, cents=True)} Aeroprice average{mult_txt}")
        facts.append(f"Effective fee rate rises from {P(eff_old)} to {P(eff_new)}; the new fee is set by the "
                     f"$10.50 floor on {P(comp_floor)} of these orders.")
    elif ch is not None and ch != core.CHANNEL:
        facts.append("Fee terms are known only for Aeroprice, so no fee change is shown for this channel "
                     "(assumption A5).")

    # --- before/after split when the period spans the change ---------------
    if spans:
        before = slc[slc["month"] < core.CHANGE_MONTH]
        after = slc[slc["month"] >= core.CHANGE_MONTH]
        rows.append(["Orders before → after Oct 1", f"{len(before):,} → {len(after):,}", ""])
        facts.append(f"Within this slice, orders went {len(before):,} (Jan–Sep) → {len(after):,} (Oct–Dec).")

    caveats = []
    if n < 100:
        caveats.append(f"Only {n} orders match — treat these figures as a small, noisy sample.")

    # --- chart only when the slice spans >= 3 months -----------------------
    fig = None
    month_span = slc["month"].nunique()
    if month_span >= 3:
        fig = _segment_trend_fig(slc, echo)

    data_tbl = pd.DataFrame(rows, columns=["Metric", "This segment", f"{ref_name} average"])
    headline = (f"{echo['carrier']}, {echo['channel']}, {echo['period']}: {s['orders']:,} orders "
                f"({P(share)} of {ref_name})"
                + (f", Aeroprice fee change {U(values.get('fee_delta_per_order', 0), signed=True, cents=True)}/order."
                   if fee_shown else "."))
    return Envelope(headline=headline, data=data_tbl, facts=facts, caveats=caveats,
                    meta=_meta(filters=echo, n_orders=n,
                               definitions="benchmark column = same metric over the whole channel"),
                    fig=fig, values=values)


def _segment_trend_fig(slc, echo):
    import plotly.graph_objects as go
    g = slc.groupby("month").agg(orders=("Number of Passengers", "size"),
                                 fee_delta=("fee_delta", "sum")).reindex(range(1, 13))
    xs = [core.MONTH_NAMES[m - 1] for m in g.index]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=xs, y=g["orders"], name="Orders", marker_color=core.COLORS["brand"]))
    fig.add_vline(x=8.5, line_dash="dot", line_color="#444",
                  annotation_text="new fee starts", annotation_position="top left")
    fig.update_yaxes(title_text="Orders per month")
    return core.style_fig(fig, f"Monthly orders — {echo['carrier']}, {echo['channel']}", height=400)


# --------------------------------------------------------------------------- #
# 8. get_methodology
# --------------------------------------------------------------------------- #
def get_methodology() -> Envelope:
    total = data.TOTAL_ORDERS
    excluded = data.ZERO_TICKET_ORDERS
    facts = [
        "A1 — Total ticket value = base fare + tax. A2 — the fee is applied per order (per-passenger is an "
        "appendix sensitivity only). A3 — old fee = min(4% × ticket, $24); new fee = clip(3.8% × ticket, "
        "$10.50, $19). A4 — impact is a counterfactual: both fee schemes are applied to the SAME orders, so "
        "it is immune to seasonality and mix. A5 — fee terms are known ONLY for Aeroprice; other channels' "
        "fees are not in the data.",
        f"'Cheap fare' means a ticket under ${core.BREAKEVEN:,.2f}. That is the exact break-even: the new "
        f"$10.50 minimum equals 4% of ${core.BREAKEVEN:,.2f}, so below it the new floor beats the old rate "
        "and the order pays more.",
        "The behaviour analysis compares Aeroprice against a control channel (Google Flights) that had no "
        "fee change, so a drop in Aeroprice beyond the control's is attributable to the fee.",
        f"Scope: BudgetAir.us 2022 orders — {total:,} in total, of which {excluded} zero-ticket orders are "
        "flagged and excluded from the fee maths.",
    ]
    caveats = ["Fee figures are a counterfactual on 2022 orders, not a forecast; the tools do not predict "
               "future periods."]
    data_tbl = pd.DataFrame([
        ["Old fee", "min(4% × ticket, $24), floor $0"],
        ["New fee", "clip(3.8% × ticket, $10.50, $19)"],
        ["Break-even", f"${core.BREAKEVEN:,.2f} (= $10.50 ÷ 4%)"],
        ["Cap binds from", f"${core.CAP_MIN:,.0f} ticket"],
        ["Change date", core.CHANGE_DATE],
    ], columns=["Term", "Definition"])
    return Envelope(
        headline="How the numbers are built: both fee schemes applied to the same 2022 orders "
                 "(a counterfactual), with a no-fee-change control channel for behaviour.",
        data=data_tbl, facts=facts, caveats=caveats,
        meta=_meta(period="method & scope", n_orders=total,
                   definitions="counterfactual + control-channel comparison"),
        values={"total_orders": total, "excluded": excluded},
    )


# --------------------------------------------------------------------------- #
# 9. get_data_catalog
# --------------------------------------------------------------------------- #
def get_data_catalog() -> Envelope:
    ch_rows = data.channel_catalog()
    carriers, n_carriers = data.carrier_catalog(top=12)
    data_tbl = pd.DataFrame([[r["channel"], f"{r['orders']:,}"] for r in ch_rows],
                            columns=["Channel", "Orders (non-zero)"])
    facts = [
        "Channels: " + ", ".join(r["channel"] for r in ch_rows) + ".",
        f"Carriers: {n_carriers} in total. Top by volume — "
        + ", ".join(f"{c['airline']} ({c['code']}, {c['orders']:,})" for c in carriers[:8]) + ".",
        "Months: 2022-01 … 2022-12. Ticket zones: " + ", ".join(data.ZONES_PLAIN)
        + ". Journey types: " + ", ".join(data.JOURNEY_TYPES)
        + ". Dimensions for winners_losers: " + ", ".join(data.DIMENSIONS) + ".",
    ]
    return Envelope(
        headline=f"The data covers {data.TOTAL_ORDERS:,} BudgetAir.us orders across "
                 f"{len(ch_rows)} channels and {n_carriers} carriers, all in 2022.",
        data=data_tbl, facts=facts,
        meta=_meta(period="2022-01 … 2022-12", n_orders=data.TOTAL_ORDERS,
                   definitions="use these exact values as tool inputs"),
        values={"n_channels": len(ch_rows), "n_carriers": n_carriers,
                "total_orders": data.TOTAL_ORDERS},
    )
