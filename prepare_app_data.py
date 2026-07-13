"""One-off prep step: read the 30MB order-level fact table ONCE and write small,
chart-ready CSVs to data/outputs/app_data/ so the Streamlit app never has to touch
the big file. Run this before the dashboard:

    python prepare_app_data.py

Re-run it whenever analysis.py regenerates the deliverable CSVs.
"""
import pandas as pd

from utils import (
    APP_DATA_DIR, OUTPUTS_DIR, CHANNEL, CONTROL_CHANNEL, DIRECT_CHANNEL,
    BREAKEVEN, ZONES, ZONE_PLAIN, CARRIER_NAMES,
)

ENRICHED_CSV = OUTPUTS_DIR / "orders_compiled_enriched.csv"


def _month(series):
    return series.astype(str).str[5:7].astype(int)


def main():
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Reading {ENRICHED_CSV} ...")
    df = pd.read_csv(ENRICHED_CSV)
    df["month"] = _month(df["sales_month"])

    # Aeroprice orders that carry a fee (non-zero ticket) — the fee analysis universe.
    ae = df[(df["Channel"] == CHANNEL) & (~df["is_zero_ticket"])].copy()

    # ---- carrier_impact.csv : top-10 Aeroprice carriers by order volume ------
    car = (
        ae.groupby("Fare Carrier")
        .agg(
            orders=("Order Number", "size"),
            avg_delta=("fee_delta", "mean"),
            total_delta=("fee_delta", "sum"),
            median_ticket=("total_ticket_value", "median"),
        )
        .sort_values("orders", ascending=False)
        .head(10)
        .reset_index()
    )
    car["carrier"] = car["Fare Carrier"].map(CARRIER_NAMES).fillna(car["Fare Carrier"])
    car = car[["Fare Carrier", "carrier", "orders", "avg_delta", "total_delta", "median_ticket"]]
    car = car.rename(columns={"Fare Carrier": "carrier_code"})
    _write(car, "carrier_impact.csv")

    # ---- dimension_impact.csv : fee delta by journey / geography / zone ------
    rows = []
    for cat, sub in ae.groupby("Journey Type"):
        rows.append(("Journey type", cat, len(sub), sub["fee_delta"].mean(), sub["fee_delta"].sum()))
    for is_intl, sub in ae.groupby("is_international"):
        label = "International" if is_intl else "Domestic"
        rows.append(("Domestic vs International", label, len(sub), sub["fee_delta"].mean(), sub["fee_delta"].sum()))
    for zone in ZONES:
        sub = ae[ae["ticket_zone"] == zone]
        rows.append(("Ticket price zone", ZONE_PLAIN[zone], len(sub), sub["fee_delta"].mean(), sub["fee_delta"].sum()))
    dim = pd.DataFrame(rows, columns=["dimension", "category", "orders", "avg_delta", "total_delta"])
    _write(dim, "dimension_impact.csv")

    # ---- monthly_cheap_by_channel.csv : cheap-fare (<break-even) volume ------
    cheap = df[(~df["is_zero_ticket"]) & (df["total_ticket_value"] < BREAKEVEN)]
    by_ch = cheap.groupby(["Channel", "month"]).size().reset_index(name="orders")
    total = cheap.groupby("month").size().reset_index(name="orders")
    total["Channel"] = "All channels"
    monthly_cheap = pd.concat([by_ch, total[["Channel", "month", "orders"]]], ignore_index=True)
    monthly_cheap = monthly_cheap.sort_values(["Channel", "month"])
    _write(monthly_cheap, "monthly_cheap_by_channel.csv")

    # ---- aeroprice_monthly.csv : per-month totals for the fee channel --------
    aem = (
        ae.groupby("month")
        .agg(
            orders=("Order Number", "size"),
            median_ticket=("total_ticket_value", "median"),
            fee_old=("fee_old_scheme", "sum"),
            fee_new=("fee_new_scheme", "sum"),
            fee_delta=("fee_delta", "sum"),
        )
        .reset_index()
    )
    _write(aem, "aeroprice_monthly.csv")

    # ---- direct_share.csv : Direct's share of all cheap-fare orders / month --
    direct_cheap = (
        cheap[cheap["Channel"] == DIRECT_CHANNEL].groupby("month").size()
        .reindex(range(1, 13), fill_value=0)
    )
    total_cheap = cheap.groupby("month").size().reindex(range(1, 13), fill_value=0)
    ds = pd.DataFrame({
        "month": range(1, 13),
        "direct_cheap": direct_cheap.values,
        "total_cheap": total_cheap.values,
    })
    ds["share_pct"] = ds["direct_cheap"] / ds["total_cheap"] * 100
    _write(ds, "direct_share.csv")

    # ---- zone_summary.csv : the 3-zone commercial picture --------------------
    total_orders = len(ae)
    zrows = []
    for zone in ZONES:
        sub = ae[ae["ticket_zone"] == zone]
        zrows.append({
            "zone": zone,
            "zone_plain": ZONE_PLAIN[zone],
            "orders": len(sub),
            "share_pct": len(sub) / total_orders * 100,
            "avg_delta": sub["fee_delta"].mean(),
            "total_delta": sub["fee_delta"].sum(),
            "avg_margin": sub["Margin"].mean(),
        })
    _write(pd.DataFrame(zrows), "zone_summary.csv")

    # ---- headline_stats.csv : a few scalars that need the order-level file ---
    sub = ae[ae["total_ticket_value"] < 100]           # sub-$100 tickets
    cheap = ae[ae["total_ticket_value"] < BREAKEVEN]    # cheap-fare Aeroprice orders
    stats = {
        # effective fee = total fee / total ticket value across the segment
        "sub100_eff_old_pct": sub["fee_old_scheme"].sum() / sub["total_ticket_value"].sum() * 100,
        "sub100_eff_new_pct": sub["fee_new_scheme"].sum() / sub["total_ticket_value"].sum() * 100,
        "sub100_share_pct": len(sub) / len(ae) * 100,
        "sub100_avg_delta": sub["fee_delta"].mean(),
        "sub100_avg_margin": sub["Margin"].mean(),
        # average new-scheme fee on a cheap Aeroprice order (Page 5 calculator)
        "avg_cheap_fee_new": cheap["fee_new_scheme"].mean(),
    }
    stat_df = pd.DataFrame({"stat": list(stats.keys()), "value": list(stats.values())})
    _write(stat_df, "headline_stats.csv")

    print("\nDone. App-data files written to", APP_DATA_DIR)


def _write(frame, name):
    path = APP_DATA_DIR / name
    frame.to_csv(path, index=False)
    print(f"  wrote {name:32s} {len(frame):>4d} rows")


if __name__ == "__main__":
    main()
