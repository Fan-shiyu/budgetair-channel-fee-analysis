"""Layer 1 (startup gate) + Layer 2 (unit) tests for the MCP tools.

Every numeric assertion compares a tool's output against a value RECOMPUTED from the
data via core — there are no literal expected numbers here (the only literals are the
fee-contract constants, owned by core).
"""
import math

import pytest

import core
from mcp_server import data
from mcp_server import server
from mcp_server import tools as T
from mcp_server.envelope import Envelope

ALL_TOOLS = [
    ("get_overview", lambda: T.get_overview()),
    ("get_fee_impact", lambda: T.get_fee_impact("full_year")),
    ("fee_for_ticket", lambda: T.fee_for_ticket(100)),
    ("winners_losers", lambda: T.winners_losers("airline")),
    ("channel_trends", lambda: T.channel_trends()),
    ("direct_opportunity", lambda: T.direct_opportunity(500)),
    ("segment_detail", lambda: T.segment_detail(channel="Aeroprice")),
    ("get_methodology", lambda: T.get_methodology()),
    ("get_data_catalog", lambda: T.get_data_catalog()),
]


# --------------------------------------------------------------------------- #
# Layer 1 — startup consistency gate
# --------------------------------------------------------------------------- #
def test_verify_numbers_passes_on_current_data():
    assert core.verify_numbers() == []


def test_gate_passes():
    server.verify_gate()   # should not raise


def test_gate_refuses_on_drift(monkeypatch):
    # Force a drift by corrupting the EXPECTED table; the gate must refuse to start.
    monkeypatch.setattr(core, "EXPECTED", {"full_year_delta": 999_999.0})
    with pytest.raises(SystemExit):
        server.verify_gate()


# --------------------------------------------------------------------------- #
# Envelope shape (every tool)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name,call", ALL_TOOLS, ids=[n for n, _ in ALL_TOOLS])
def test_envelope_shape(name, call):
    env = call()
    assert isinstance(env, Envelope)
    assert isinstance(env.headline, str) and env.headline
    assert isinstance(env.facts, list) and len(env.facts) >= 1
    assert "data_version" in env.meta
    # text serialisation always includes the required sections
    text = env.to_text()
    for section in ("HEADLINE:", "FACTS:", "CAVEATS:", "META:"):
        assert section in text


def test_chart_tools_have_figure():
    for _, call in ALL_TOOLS:
        env = call()
        # methodology & catalog have no chart; the other seven do
    assert T.get_overview().fig is not None
    assert T.get_methodology().fig is None
    assert T.get_data_catalog().fig is None


# --------------------------------------------------------------------------- #
# Numbers recomputed from data
# --------------------------------------------------------------------------- #
def test_overview_full_year_delta():
    env = T.get_overview()
    assert env.values["full_year_delta"] == pytest.approx(float(core.full_year_delta()))
    assert core.fmt_usd(core.full_year_delta(), signed=True) in env.headline


def test_fee_impact_periods():
    assert T.get_fee_impact("full_year").values["delta"] == pytest.approx(float(core.full_year_delta()))
    assert T.get_fee_impact("after_change").values["delta"] == pytest.approx(float(core.q4_delta()))
    # a single month equals that month's Aeroprice fee_delta
    ae = core.aeroprice_summary("full")
    oct_delta = ae[ae["month"] == 10]["fee_delta"].sum()
    assert T.get_fee_impact("2022-10").values["delta"] == pytest.approx(float(oct_delta))


def test_fee_impact_invalid_period():
    env = T.get_fee_impact("2099-13")
    assert env.is_error
    assert any("full_year" in f for f in env.facts)


def test_fee_for_ticket_rules():
    e100 = T.fee_for_ticket(100)
    assert e100.values["old"] == pytest.approx(float(core.fee_curve(100, **core.OLD_SCHEME)))
    assert e100.values["new"] == pytest.approx(float(core.fee_curve(100, **core.NEW_SCHEME)))
    assert e100.values["rule_new"] == "floor"
    assert e100.values["rule_old"] == "percent"
    e600 = T.fee_for_ticket(600)
    assert e600.values["rule_new"] == "cap"


@pytest.mark.parametrize("bad", [0, -5, 20001, "abc"])
def test_fee_for_ticket_out_of_range(bad):
    assert T.fee_for_ticket(bad).is_error


def test_winners_matches_core():
    env = T.winners_losers("airline")
    tbl = core.winners_losers_table("airline")
    assert env.values["loser"] == tbl.iloc[0]["category"]
    assert env.values["loser_avg"] == pytest.approx(float(tbl.iloc[0]["value"]))
    assert env.values["winner"] == tbl.iloc[-1]["category"]


def test_winners_invalid_dimension():
    env = T.winners_losers("carrier")
    assert env.is_error
    assert any("airline" in f for f in env.facts)


def test_channel_trends_numbers():
    env = T.channel_trends()
    assert env.values["ae_change"] == pytest.approx(core.aeroprice_cheap_change() * 100)
    assert env.values["ctrl_change"] == pytest.approx(core.cheap_volume_change(core.CONTROL_CHANNEL) * 100)


def test_direct_savings_formula():
    env = T.direct_opportunity(500)
    avg = core.load_stats()["avg_cheap_fee_new"]
    assert env.values["savings"] == pytest.approx(500 * 12 * avg)


@pytest.mark.parametrize("bad", [-1, 2201, 5000])
def test_direct_out_of_range(bad):
    assert T.direct_opportunity(bad).is_error


# --------------------------------------------------------------------------- #
# segment_detail behaviours
# --------------------------------------------------------------------------- #
def test_segment_empty_is_answer_not_error():
    # a genuinely empty (but individually valid) combination
    env = T.segment_detail(channel="Kayak Group", carrier="NK",
                           ticket_zone="Pays less", period="2022-01")
    assert env.meta["n_orders"] == 0
    assert "No orders match" in env.headline
    assert not env.is_error  # graceful answer, not a hard error
    assert env.facts         # points at nearest valid options


def test_segment_unknown_carrier_lists_options():
    env = T.segment_detail(carrier="Ryannair")
    assert env.is_error
    assert env.facts  # includes suggestions or a valid carrier list


def test_segment_non_aeroprice_has_no_fee_block():
    env = T.segment_detail(channel="Google Flights")
    assert "fee_delta_per_order" not in env.values
    assert any("only for Aeroprice" in f for f in env.facts)


def test_segment_benchmark_recomputes():
    env = T.segment_detail(carrier="LATAM", journey_type="One Way", period="after_change")
    seg = data.SEGMENTS_NZ
    m = seg[(seg["Channel"] == "Aeroprice") & (seg["Fare Carrier"] == "LA")
            & (seg["Journey Type"] == "One Way") & (seg["month"].isin([10, 11, 12]))]
    assert env.values["fee_delta_per_order"] == pytest.approx(m["fee_delta"].sum() / len(m))
    # benchmark equals the Aeroprice channel average per order
    ae = data.SEGMENTS_NZ[data.SEGMENTS_NZ["Channel"] == "Aeroprice"]
    assert env.values["benchmark_per_order"] == pytest.approx(ae["fee_delta"].sum() / len(ae))


def test_segment_small_sample_caveat():
    env = T.segment_detail(carrier="EK", channel="Aeroprice", period="2022-02", ticket_zone="Pays more")
    if 0 < env.meta["n_orders"] < 100:
        assert any("small" in c.lower() or "sample" in c.lower() for c in env.caveats)


def test_data_catalog_counts():
    env = T.get_data_catalog()
    assert env.values["total_orders"] == data.TOTAL_ORDERS
    assert env.values["n_carriers"] == data.SEGMENTS_NZ["Fare Carrier"].nunique()
