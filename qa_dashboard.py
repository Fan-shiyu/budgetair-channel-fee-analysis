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
import struct
import sys
from pathlib import Path

import numpy as np
from playwright.sync_api import sync_playwright

import utils as u

VIEWPORT_H = 1000   # base viewport height; long pages are captured taller than this

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8501"
IS_REMOTE = not any(h in BASE for h in ("localhost", "127.0.0.1"))
# Deployed runs write to a separate folder so the committed local screenshots
# (used for slides) are never overwritten.
SHOTS = Path("qa_screenshots_deployed" if IS_REMOTE else "qa_screenshots")
SHOTS.mkdir(exist_ok=True)
# Timeouts only (never assertion logic): the Streamlit free tier is slower and can
# cold-start for 30-60s, so give the deployed app generous navigation/render budgets.
NAV_TIMEOUT = 120_000 if IS_REMOTE else 30_000
CHART_TIMEOUT = 30_000 if IS_REMOTE else 15_000

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
    try:
        # Streamlit keeps a websocket open, so on the deployed app 'networkidle' may not
        # fire — tolerate a timeout rather than crash (this is a settle heuristic only).
        page.wait_for_load_state("networkidle", timeout=10_000)
    except Exception:
        pass
    try:
        page.wait_for_selector('[data-testid="stStatusWidget"]', state="detached", timeout=8000)
    except Exception:
        pass
    page.wait_for_timeout(400)


def resolve_app_base(page):
    """Return the URL that serves the app as the TOP-LEVEL document.

    Streamlit Community Cloud wraps the app in an embed iframe (path '/~/+/'); the public
    URL's main frame is just hosting chrome. Navigating straight to the embed path renders
    the app top-level (no iframe), which is what the QA drives."""
    page.goto(BASE, wait_until="domcontentloaded")
    for _ in range(NAV_TIMEOUT // 2500):
        if page.locator('[data-testid="stMetric"]').count() > 0:
            return BASE  # already top-level
        for fr in page.frames:
            if "/~/+/" in fr.url:
                return fr.url.split("/~/+/")[0] + "/~/+"
        page.wait_for_timeout(2500)
    return BASE


def counts(page):
    return {
        "err": page.locator('[data-testid="stException"], .stException').count(),
        "charts": page.locator(".js-plotly-plot").count(),
        "kpis": page.locator('[data-testid="stMetric"]').count(),
    }


def render_ready(page, n_charts):
    """Wait until the expected Plotly charts exist AND have drawn real content."""
    if not n_charts:
        return
    page.wait_for_function(
        """n => {
            const ps = document.querySelectorAll('.js-plotly-plot');
            return ps.length >= n && [...ps].every(p => {
                const svg = p.querySelector('svg.main-svg');
                return svg && svg.querySelectorAll('path, rect, .point, .trace').length > 0;
            });
        }""",
        arg=n_charts, timeout=CHART_TIMEOUT,
    )


def _content_height(page):
    return page.evaluate(
        """() => {
            const sels = ['[data-testid="stMain"]', '[data-testid="stAppViewContainer"]',
                          'section.main', '[data-testid="stApp"]'];
            let h = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
            for (const s of sels) { const e = document.querySelector(s); if (e) h = Math.max(h, e.scrollHeight); }
            return h;
        }"""
    )


def _scroll_cycle(page):
    """Force lazy-rendered elements in by scrolling to the bottom and back."""
    page.evaluate(
        """() => new Promise(res => {
            const e = document.querySelector('[data-testid="stMain"]') || document.scrollingElement;
            e.scrollTo(0, e.scrollHeight); window.scrollTo(0, document.body.scrollHeight);
            setTimeout(() => { e.scrollTo(0, 0); window.scrollTo(0, 0); res(); }, 350);
        })"""
    )


def capture_full(page, path, n_charts):
    """Screenshot the ENTIRE page height (Streamlit scrolls inside an inner
    container, so plain full_page only grabs one viewport). We grow the viewport
    to the content height, then capture."""
    render_ready(page, n_charts)
    _scroll_cycle(page)
    page.wait_for_timeout(300)
    h = int(_content_height(page)) + 60
    page.set_viewport_size({"width": 1280, "height": h})
    page.wait_for_timeout(350)
    render_ready(page, n_charts)
    page.screenshot(path=str(path), full_page=True)
    page.set_viewport_size({"width": 1280, "height": VIEWPORT_H})


def png_height(path):
    with open(path, "rb") as f:
        return struct.unpack(">I", f.read(24)[20:24])[0]


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
        page.set_default_navigation_timeout(NAV_TIMEOUT)

        base = BASE
        if IS_REMOTE:
            # Wake the app first: the Streamlit free tier sleeps after inactivity and the
            # first load can take 30-60s. Resolve the real app URL (Cloud serves it in an
            # embed frame) and wait generously for the home KPIs — timeouts only.
            print(f"Waking {BASE} (cold start can take 30-60s)...")
            base = resolve_app_base(page)
            if base != BASE:
                print(f"App is served in an embed frame; driving it directly at {base}")
            page.goto(f"{base}/", wait_until="domcontentloaded")
            page.wait_for_selector('[data-testid="stMetric"]', timeout=NAV_TIMEOUT)
            settle(page)
            print("App is awake; starting QA.")

        for slug, shot, want in PAGES:
            print(f"\n== {shot} ==")
            page.goto(f"{base}/{slug}")
            settle(page)
            if want["charts"]:
                page.wait_for_selector(".js-plotly-plot", timeout=CHART_TIMEOUT)
                page.wait_for_timeout(300)
            c = counts(page)
            check(c["err"] == 0, f"{shot}: no Streamlit exception")
            check(c["charts"] == want["charts"], f"{shot}: {c['charts']} charts (want {want['charts']})")
            check(c["kpis"] == want["kpis"], f"{shot}: {c['kpis']} KPI cards (want {want['kpis']})")
            guard_arrows(page, shot)
            shot_path = SHOTS / f"{shot}.png"
            capture_full(page, shot_path, want["charts"])
            check(png_height(shot_path) > VIEWPORT_H,
                  f"{shot}: screenshot is full-height ({png_height(shot_path)}px > {VIEWPORT_H})")
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
                vis = page.evaluate(
                    """() => {
                        const sb = document.querySelector('[data-testid="stSelectbox"]');
                        const label = sb && sb.querySelector('label');
                        const val = sb && sb.querySelector('[data-baseweb="select"]');
                        const shown = e => !!e && e.offsetWidth > 0 && e.offsetHeight > 0
                                            && e.innerText.trim() !== '';
                        return { label: shown(label) && label.innerText.includes('View by'),
                                 value: shown(val) };
                    }"""
                )
                check(vis["label"] and vis["value"],
                      "'View by:' label and selected value are visible (not an empty box)")
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
