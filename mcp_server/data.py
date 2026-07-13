"""Data access + input resolution for the MCP tools.

Loads the small parquet segment table (and reuses core's cached CSV loaders) ONCE at
import. Provides the enum catalogs, period/carrier/enum resolvers, and a content-hash
data_version. Everything here is deterministic and read-only; no raw order rows leave.
"""
import difflib
import hashlib
from functools import lru_cache

import pandas as pd

import core

# --------------------------------------------------------------------------- #
# Order-level segment table (subset parquet). Loaded once; fee aggregates use the
# non-zero-ticket universe (matching the dashboard / analysis).
# --------------------------------------------------------------------------- #
SEGMENTS = pd.read_parquet(core.SEGMENTS_PARQUET)
SEGMENTS_NZ = SEGMENTS[~SEGMENTS["is_zero_ticket"]].copy()

# --------------------------------------------------------------------------- #
# Enum catalogs (derived from data, not hardcoded)
# --------------------------------------------------------------------------- #
CHANNELS = (SEGMENTS_NZ["Channel"].value_counts().index.tolist())   # by volume, desc
MONTHS = [f"2022-{m:02d}" for m in range(1, 13)]
ZONES_PLAIN = [core.ZONE_PLAIN[z] for z in core.ZONES]              # Pays more / About even / Pays less
JOURNEY_TYPES = sorted(SEGMENTS_NZ["Journey Type"].dropna().unique().tolist())
DOMESTIC_INTL = ["Domestic", "International"]
DIMENSIONS = ["airline", "journey_type", "domestic_international", "ticket_zone"]

PERIOD_KEYWORDS = ["full_year", "before_change", "after_change"]
VALID_PERIODS = PERIOD_KEYWORDS + MONTHS

_VALID_CARRIER_CODES = set(SEGMENTS_NZ["Fare Carrier"].dropna().unique())
_NAME_TO_CODE = {name.lower(): code for code, name in core.CARRIER_NAMES.items()}


@lru_cache(maxsize=1)
def data_version():
    """Stable content hash of the source data files (12-char) for the meta block."""
    h = hashlib.md5()
    files = [core.SUMMARY_CSV, core.SEGMENTS_PARQUET] + sorted(core.APP_DATA_DIR.glob("*.csv"))
    for p in files:
        h.update(p.read_bytes())
    return h.hexdigest()[:12]


TOTAL_ORDERS = int(len(SEGMENTS))
ZERO_TICKET_ORDERS = int(SEGMENTS["is_zero_ticket"].sum())


# --------------------------------------------------------------------------- #
# Resolvers
# --------------------------------------------------------------------------- #
def resolve_period(period):
    """Return (months:list[int], label:str, spans_change:bool).

    Raises ValueError (message lists valid options) on anything invalid.
    """
    p = str(period).strip()
    if p == "full_year":
        return list(range(1, 13)), "full year (all 2022)", True
    if p == "before_change":
        return list(core.PRE_MONTHS), "before the change (Jan–Sep 2022)", False
    if p == "after_change":
        return list(core.POST_MONTHS), "after the change (Oct–Dec 2022)", False
    if p in MONTHS:
        mm = int(p[-2:])
        return [mm], f"{core.MONTH_NAMES[mm - 1]} 2022", False
    raise ValueError(
        "Invalid period '" + p + "'. Valid values: full_year, before_change, after_change, "
        "or a month 2022-01 … 2022-12."
    )


def resolve_carrier(text):
    """Resolve a carrier code or airline name against the data.

    Returns (code, name, suggestions):
      - exact/known match  -> (CODE, Name, None)
      - no match           -> (None, None, [up to 5 suggestions])
    """
    t = str(text).strip()
    up = t.upper()
    if up in _VALID_CARRIER_CODES:
        return up, core.CARRIER_NAMES.get(up, up), None
    low = t.lower()
    if low in _NAME_TO_CODE and _NAME_TO_CODE[low] in _VALID_CARRIER_CODES:
        code = _NAME_TO_CODE[low]
        return code, core.CARRIER_NAMES[code], None
    # fuzzy: try known names and codes
    known_names = [core.CARRIER_NAMES[c] for c in core.CARRIER_NAMES if c in _VALID_CARRIER_CODES]
    close = difflib.get_close_matches(t.title(), known_names, n=5, cutoff=0.6)
    close += difflib.get_close_matches(up, sorted(_VALID_CARRIER_CODES), n=5, cutoff=0.6)
    seen, suggestions = set(), []
    for c in close:
        if c not in seen:
            seen.add(c)
            suggestions.append(c)
    return None, None, suggestions[:5]


def resolve_enum(value, valid, label):
    """Case-insensitive resolve of a value against a small enum; ValueError lists options."""
    if value is None:
        return None
    for v in valid:
        if str(value).strip().lower() == v.lower():
            return v
    raise ValueError(f"Invalid {label} '{value}'. Valid values: {', '.join(valid)}.")


def carrier_catalog(top=25):
    """Top carriers by non-zero order count, with names."""
    counts = SEGMENTS_NZ["Fare Carrier"].value_counts()
    rows = []
    for code, n in counts.head(top).items():
        rows.append({"code": code, "airline": core.CARRIER_NAMES.get(code, code), "orders": int(n)})
    return rows, int(counts.size)


def channel_catalog():
    counts = SEGMENTS_NZ["Channel"].value_counts()
    return [{"channel": c, "orders": int(n)} for c, n in counts.items()]
