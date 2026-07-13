"""Reusable browser QA for the BudgetAir dashboard (Playwright, Python sync API).

Run it against a live app:

    pip install playwright && playwright install chromium
    python prepare_app_data.py
    streamlit run app.py --server.headless true      # in one terminal
    python qa_dashboard.py                            # in another

It visits all six pages, asserts no Streamlit exception is rendered, checks the
expected number of KPI cards and charts, drives every interactive control, guards
against inverted delta arrows, and saves a full-page screenshot per page to
qa_screenshots/.

KPI values are checked against the same computed figures + fmt_* helpers the app
uses (utils.*), never against hardcoded literals — so this test drifts with the
data exactly like the app does.

Pass a different base URL as the first argument to QA a deployed app:
    python qa_dashboard.py https://your-app.streamlit.app
"""
import sys
from pathlib import Path

import numpy as np
from playwright.sync_api import sync_playwright

import utils as u

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8501"
SHOTS = Path("qa_screenshots")
SHOTS.mkdir(exist_ok=True)

# Expected computed values (formatted with the app's own helpers) -------------
FULL = u.fmt_usd(u.full_year_delta(), signed=True)                       # +$131,696
Q4 = u.fmt_usd(u.q4_delta(), signed=True)                                # -$1,768
AE_CHANGE = u.fmt_pct(u.aeroprice_cheap_change() * 100, signed=True)     # -58.5%
CTRL_CHANGE = u.fmt_pct(u.cheap_volume_change(u.CONTROL_CHANNEL) * 100, signed=True)  # -5.1%

_pre = u.aeroprice_summary("pre")
AVG_PRE = u.fmt_usd(_pre["fee_delta"].sum() / _pre["orders"].sum(), signed=True, cents=True)  # +$2.85

SHARE_PRE = u.fmt_pct(u.cheap_share_pooled(u.PRE_MONTHS) * 100)          # 72.6%
SHARE_POST = u.fmt_pct(u.cheap_share_pooled(u.POST_MONTHS) * 100)        # 51.1%
SHARE_PP = u.fmt_pp((u.cheap_share_pooled(u.POST_MONTHS)
                     - u.cheap_share_pooled(u.PRE_MONTHS)) * 100)        # -21.5 pp
AE_CHANGE_R = u.fmt_pct(u.aeroprice_cheap_change() * 100, decimals=0)    # -59%

_ds = u.load_direct_share().sort_values("month")
_p = _ds[_ds["month"] <= 9]
_slope, _int = np.polyfit(_p["month"], _p["share_pct"], 1)
DIRECT_PP = u.fmt_pp(_ds.set_index("month").loc[12, "share_pct"] - (_slope * 12 + _int))  # +1.6 pp

PAGES = [
    ("", "0_home", {"charts": 0, "kpis": 4}),
    ("The_Fee_Change", "1_the_fee_change", {"charts": 1, "kpis": 2}),
    ("Overall_Impact", "2_overall_impact", {"charts": 2, "kpis": 4}),
    ("Winners_and_Losers", "3_winners_and_losers", {"charts": 1, "kpis": 3}),
    ("What_Happened", "4_what_happened", {"charts": 2, "kpis": 3}),
    ("Direct_Opportunity", "5_direct_opportunity", {"charts": 1, "kpis": 2}),
]

results = []


def check(cond, msg):
    results.append((cond, msg))
    print(("  PASS " if cond else "  FAIL ") + msg)


def settle(page):
    """Wait for Streamlit to finish its rerun (the 'Running' status disappears)."""
    page.wait_for_load_state("networkidle")
    try:
        page.wait_for_selector('[data-testid="stStatusWidget"]', state="detached", timeout=8000)
    except Exception:
        pass
    page.wait_for_timeout(400)


def counts(page):
    return {
        "err": page.locator('[data-testid="stException"], .stException').count(),
        "charts": page.locator(".js-plotly-plot").count(),
        "kpis": page.locator('[data-testid="stMetric"]').count(),
    }


def metric_deltas(page):
    """Each KPI's delta text + arrow direction ('up'/'down'/'none')."""
    return page.evaluate(
        """() => [...document.querySelectorAll('[data-testid="stMetric"]')].map(m => {
             const d = m.querySelector('[data-testid="stMetricDelta"]');
             const up = m.querySelector('[data-testid="stMetricDeltaIcon-Up"]');
             const down = m.querySelector('[data-testid="stMetricDeltaIcon-Down"]');
             return { text: d ? d.innerText.trim() : null,
                      arrow: up ? 'up' : (down ? 'down' : 'none') };
           })"""
    )


def guard_arrows(page, shot):
    """Regression guard (item 5/17): a delta that starts with '-' must point DOWN,
    one that starts with '+' must point UP. No inverted arrows on falling metrics."""
    ok = True
    for d in metric_deltas(page):
        t, arrow = d["text"], d["arrow"]
        if not t:
            continue
        if t.startswith("-") and arrow == "up":
            ok = False
        if t.startswith("+") and arrow == "down":
            ok = False
    check(ok, f"{shot}: no inverted delta arrows")


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 1000})

        for slug, shot, want in PAGES:
            print(f"\n== {shot} ==")
            page.goto(f"{BASE}/{slug}")
            settle(page)
            if want["charts"]:
                page.wait_for_selector(".js-plotly-plot", timeout=15000)
                page.wait_for_timeout(300)
            c = counts(page)
            check(c["err"] == 0, f"{shot}: no Streamlit exception")
            check(c["charts"] == want["charts"], f"{shot}: {c['charts']} charts (want {want['charts']})")
            check(c["kpis"] == want["kpis"], f"{shot}: {c['kpis']} KPI cards (want {want['kpis']})")
            guard_arrows(page, shot)
            page.screenshot(path=str(SHOTS / f"{shot}.png"), full_page=True)
            body = page.locator("body").inner_text()

            if slug == "":
                check(FULL in body, f"home shows full-year cost {FULL}")
                check(AE_CHANGE in body, f"home shows cheap-fare change {AE_CHANGE}")
                check(AE_CHANGE_R in body, f"home shows rounded cheap-fare volume {AE_CHANGE_R}")

            if slug == "The_Fee_Change":
                inp = page.locator('input[type="number"]')
                inp.fill("100"); inp.press("Enter"); settle(page)
                body = page.locator("body").inner_text()
                check("$4.00" in body and "$10.50" in body, "ticket 100 -> old $4.00 / new $10.50")

            if slug == "Overall_Impact":
                check(AVG_PRE in body, f"shows per-order cost with cents {AVG_PRE}")
                page.get_by_text("After the change only").click(); settle(page)
                title = page.locator(".gtitle").first.text_content()
                check(Q4 in title, f"radio 'after change' -> waterfall net {Q4}")
                page.get_by_text("Full year", exact=True).click(); settle(page)

            if slug == "Winners_and_Losers":
                for opt in ["Ticket price zone", "Journey type", "Domestic vs International", "Airline"]:
                    page.locator('[data-baseweb="select"]').click()
                    page.get_by_role("option", name=opt).click()
                    settle(page)
                    ok = page.locator('[data-testid="stException"], .stException').count() == 0
                    check(ok, f"dropdown '{opt}' re-renders without error")

            if slug == "What_Happened":
                check(SHARE_POST in body, f"share KPI shows post-change pooled {SHARE_POST}")
                check(SHARE_PRE in body, f"share KPI shows pre-change pooled {SHARE_PRE}")
                check(SHARE_PP in body, f"share KPI delta shows {SHARE_PP}")
                check("July–September average" in body or "July-September average" in body,
                      "chart caption says re-indexed to Jul-Sep average")

            if slug == "Direct_Opportunity":
                check(f"{DIRECT_PP} above trend" in body, f"Direct KPI shows '{DIRECT_PP} above trend'")
                slider = page.locator('[data-testid="stSlider"] [role="slider"]')
                slider.click(); page.keyboard.press("ArrowRight"); settle(page)
                now = int(slider.get_attribute("aria-valuenow"))
                expected = u.fmt_usd(now * 12 * u.load_stats()["avg_cheap_fee_new"])
                body = page.locator("body").inner_text()
                check(expected in body, f"slider {now} -> savings {expected}")

        browser.close()

    passed = sum(1 for ok, _ in results if ok)
    total = len(results)
    print(f"\n==== {passed}/{total} checks passed ====")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    run()
