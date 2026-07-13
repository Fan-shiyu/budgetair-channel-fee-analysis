"""Reusable browser QA for the BudgetAir dashboard (Playwright, Python sync API).

Run it against a live app:

    pip install playwright && playwright install chromium
    python prepare_app_data.py
    streamlit run app.py --server.headless true      # in one terminal
    python qa_dashboard.py                            # in another

It visits all six pages, asserts no Streamlit exception is rendered, checks the
expected number of KPI cards and charts, drives every interactive control, and
saves a full-page screenshot per page to qa_screenshots/.

KPI values are checked against utils.verify_numbers() / the same fmt_* helpers the
app uses — never against hardcoded literals — so this test drifts with the data
exactly like the app does.

Pass a different base URL as the first argument to QA a deployed app:
    python qa_dashboard.py https://your-app.streamlit.app
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

import utils as u

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8501"
SHOTS = Path("qa_screenshots")
SHOTS.mkdir(exist_ok=True)

# Expected computed values (formatted with the app's own helpers) -------------
FULL = u.fmt_usd(u.full_year_delta(), signed=True)
Q4 = u.fmt_usd(u.q4_delta(), signed=True)
AE_CHANGE = u.fmt_pct(u.aeroprice_cheap_change() * 100, signed=True)
CTRL_CHANGE = u.fmt_pct(u._cheap_change(u.CONTROL_CHANNEL) * 100, signed=True)

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


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 1000})

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
            page.screenshot(path=str(SHOTS / f"{shot}.png"), full_page=True)

            if slug == "":
                body = page.locator("body").inner_text()
                check(FULL in body, f"home shows full-year cost {FULL}")
                check(AE_CHANGE in body, f"home shows cheap-fare change {AE_CHANGE}")

            if slug == "The_Fee_Change":
                inp = page.locator('input[type="number"]')
                inp.fill("100"); inp.press("Enter"); settle(page)
                body = page.locator("body").inner_text()
                check("$4.00" in body and "$10.50" in body, "ticket 100 -> old $4.00 / new $10.50")

            if slug == "Overall_Impact":
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

            if slug == "Direct_Opportunity":
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
