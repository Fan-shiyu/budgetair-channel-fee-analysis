"""One-off prep for the MCP server's segment_detail tool.

Reads the 30MB order-level fact table ONCE and writes a small column-subset to
parquet so the server can answer arbitrary segment questions (by channel, carrier,
journey type, geography, zone, month) without ever touching the big CSV at request
time. Run after analysis.py regenerates the deliverables:

    python prepare_mcp_data.py
"""
import pandas as pd

from core import MCP_DATA_DIR, OUTPUTS_DIR

ENRICHED_CSV = OUTPUTS_DIR / "orders_compiled_enriched.csv"

# Only the columns the segment tool needs (aggregates only; never raw PII/order ids).
KEEP = [
    "Channel", "sales_month", "total_ticket_value", "ticket_zone", "Fare Carrier",
    "Journey Type", "is_international", "Margin",
    "fee_old_scheme", "fee_new_scheme", "fee_delta",
    "is_post_change", "is_zero_ticket", "Number of Passengers",
]


def main():
    MCP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Reading {ENRICHED_CSV} ...")
    df = pd.read_csv(ENRICHED_CSV, usecols=KEEP)
    df["month"] = df["sales_month"].astype(str).str[5:7].astype(int)

    # tidy dtypes to keep the parquet small and typed
    for col in ["is_international", "is_post_change", "is_zero_ticket"]:
        df[col] = df[col].astype(bool)
    for col in ["Channel", "ticket_zone", "Fare Carrier", "Journey Type", "sales_month"]:
        df[col] = df[col].astype("category")

    out = MCP_DATA_DIR / "segments.parquet"
    df.to_parquet(out, index=False, compression="snappy")
    size_mb = out.stat().st_size / 1e6
    print(f"Wrote {out}  ({len(df):,} rows, {len(df.columns)} cols, {size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
