"""
BudgetAir.us — Aeroprice Channel Fee Change Analysis (2022)
============================================================
Reproducible pipeline: loads the 12 monthly order files, cleans and enriches
them, applies the old and new Aeroprice fee schemes as a counterfactual on
identical orders, and exports the two deliverable CSVs.

Fee schemes (per contract, applied PER ORDER on Total Ticket = Base Fare + Tax):
    OLD (before 2022-10-01): fee = min(4.0% x Ticket, $24.00), minimum $0.00
    NEW (from   2022-10-01): fee = clip(3.8% x Ticket, $10.50, $19.00)

Key assumptions (documented, agreed):
    A1. Total Ticket Value = Base Fare + Tax.
    A2. Percentage, floor and cap are applied per ORDER (per-passenger shown
        as a sensitivity at the end of this script).
    A3. Orders with Ticket <= 0 (362 rows, ~0.3%) are flagged and excluded
        from fee calculations (kept in the compiled file for transparency).
    A4. 'Margin' is assumed net of all costs incl. the actual channel fee, so
        impact is measured as a counterfactual (both schemes on same orders).
    A5. Fee columns are populated ONLY for Aeroprice orders — other channels'
        fee terms are unknown and must not be invented.

Usage:  python analysis.py
Inputs: ./data/sales_2022_01.csv ... sales_2022_12.csv  (path configurable)
Outputs:
    outputs/orders_compiled_enriched.csv   (order-level fact table)
    outputs/impact_summary.csv             (month x channel x zone rollup)
"""

from pathlib import Path
import glob
import numpy as np
import pandas as pd

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
DATA_DIR = Path("data")          # folder containing the 12 monthly CSVs
OUT_DIR = Path("outputs")
CHANGE_DATE = "2022-10-01"       # fee change effective date

OLD_SCHEME = {"rate": 0.040, "floor": 0.00, "cap": 24.00}
NEW_SCHEME = {"rate": 0.038, "floor": 10.50, "cap": 19.00}

# Break-even ticket values (derived from the schemes, used for zone labels):
#   floor binds while 3.8% x T <= 10.50  ->  T <= 276.32
#   new fee > old fee while T < 262.50 (10.50 = 4% x T)
#   new cap binds from  T >= 500.00 (19 / 0.038)
LOSER_MAX = 262.50
CAP_MIN = 500.00


def channel_fee(ticket: pd.Series, rate: float, floor: float, cap: float) -> pd.Series:
    """Contractual channel fee: percentage of ticket, clipped to [floor, cap]."""
    return np.clip(ticket * rate, floor, cap)


def load_monthly_files(data_dir: Path) -> pd.DataFrame:
    """Union the 12 monthly files, keeping source-file lineage."""
    frames = []
    for path in sorted(glob.glob(str(data_dir / "sales_2022_*.csv"))):
        frame = pd.read_csv(path)
        frame["source_file"] = Path(path).name
        frames.append(frame)
    if not frames:
        raise FileNotFoundError(f"No sales_2022_*.csv files found in {data_dir}/")
    df = pd.concat(frames, ignore_index=True)
    print(f"Loaded {len(frames)} files -> {len(df):,} orders")
    return df


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Cleaning flags + engineered analysis columns (assumptions A1-A5)."""
    df = df.copy()
    df["Sales Date"] = pd.to_datetime(df["Sales Date"])
    df["Departure Date"] = pd.to_datetime(df["Departure Date"])
    df["sales_month"] = df["Sales Date"].dt.strftime("%Y-%m")
    df["is_post_change"] = df["Sales Date"] >= CHANGE_DATE

    # A1: total ticket value
    df["total_ticket_value"] = df["Base Fare"] + df["Tax"]

    # A3: transparent cleaning flag (rows kept, excluded from fee math)
    df["is_zero_ticket"] = df["total_ticket_value"] <= 0

    # Helper dimensions (all channels — used for mix/substitution analysis)
    df["is_international"] = df["Origin Country"] != df["Destination Country"]
    df["ticket_zone"] = pd.cut(
        df["total_ticket_value"],
        bins=[0, LOSER_MAX, CAP_MIN, np.inf],
        labels=["<$262.50 (fee up)", "$262.50-500 (about even)", ">$500 (fee down)"],
    )

    # A2 + A5: counterfactual fees — Aeroprice only, valid tickets only
    scope = (df["Channel"] == "Aeroprice") & (~df["is_zero_ticket"])
    t = df.loc[scope, "total_ticket_value"]
    df.loc[scope, "fee_old_scheme"] = channel_fee(t, **OLD_SCHEME)
    df.loc[scope, "fee_new_scheme"] = channel_fee(t, **NEW_SCHEME)
    df["fee_delta"] = df["fee_new_scheme"] - df["fee_old_scheme"]
    df.loc[scope, "effective_fee_rate_old"] = df.loc[scope, "fee_old_scheme"] / t
    df.loc[scope, "effective_fee_rate_new"] = df.loc[scope, "fee_new_scheme"] / t
    df.loc[scope, "margin_after_fee_delta"] = (
        df.loc[scope, "Margin"] - df.loc[scope, "fee_delta"]
    )

    # Which constraint binds under the NEW scheme (mechanism label)
    linear = df.loc[scope, "total_ticket_value"] * NEW_SCHEME["rate"]
    df.loc[scope, "fee_regime_new"] = np.select(
        [linear <= NEW_SCHEME["floor"], linear >= NEW_SCHEME["cap"]],
        ["floor", "cap"],
        default="linear",
    )
    return df


def build_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Month x channel x zone rollup — the table behind every chart."""
    valid = df[~df["is_zero_ticket"]]
    summary = (
        valid.groupby(["sales_month", "Channel", "ticket_zone"], observed=True)
        .agg(
            orders=("Order Number", "count"),
            passengers=("Number of Passengers", "sum"),
            total_ticket_value=("total_ticket_value", "sum"),
            total_margin=("Margin", "sum"),
            fee_old_scheme=("fee_old_scheme", "sum"),
            fee_new_scheme=("fee_new_scheme", "sum"),
            fee_delta=("fee_delta", "sum"),
        )
        .reset_index()
    )
    summary["fee_delta_pct_of_margin"] = np.where(
        summary["total_margin"] != 0,
        summary["fee_delta"] / summary["total_margin"] * 100,
        np.nan,
    ).round(2)
    for col in ["total_ticket_value", "total_margin", "fee_old_scheme",
                "fee_new_scheme", "fee_delta"]:
        summary[col] = summary[col].round(2)
    return summary


def print_validation(df: pd.DataFrame) -> None:
    """Headline numbers — must match the validated figures in CLAUDE.md."""
    ap = df[(df["Channel"] == "Aeroprice") & (~df["is_zero_ticket"])]
    q4, pre = ap[ap["is_post_change"]], ap[~ap["is_post_change"]]
    print("\n--- VALIDATION (must match CLAUDE.md) ---")
    print(f"Q4 orders {len(q4):,}: old ${q4['fee_old_scheme'].sum():,.0f} "
          f"new ${q4['fee_new_scheme'].sum():,.0f} delta ${q4['fee_delta'].sum():,.0f}")
    print(f"Jan-Sep {len(pre):,}: delta ${pre['fee_delta'].sum():,.0f}")
    print(f"Full-year counterfactual delta: ${ap['fee_delta'].sum():,.0f}")

    # A2 sensitivity: floor/cap applied per passenger instead of per order
    t_pp = ap["total_ticket_value"] / ap["Number of Passengers"]
    fee_old_pp = channel_fee(t_pp, **OLD_SCHEME) * ap["Number of Passengers"]
    fee_new_pp = channel_fee(t_pp, **NEW_SCHEME) * ap["Number of Passengers"]
    print(f"Sensitivity (per-passenger basis), full-year delta: "
          f"${(fee_new_pp - fee_old_pp).sum():,.0f}")


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    df = enrich(load_monthly_files(DATA_DIR))

    fact_path = OUT_DIR / "orders_compiled_enriched.csv"
    df.to_csv(fact_path, index=False)
    print(f"Wrote {fact_path} ({len(df):,} rows)")

    summary = build_summary(df)
    summary_path = OUT_DIR / "impact_summary.csv"
    summary.to_csv(summary_path, index=False)
    print(f"Wrote {summary_path} ({len(summary):,} rows)")

    print_validation(df)


if __name__ == "__main__":
    main()
