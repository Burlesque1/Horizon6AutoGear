"""Generate README screenshots from phantom.html using Playwright."""

import json
import math
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
THEME = ROOT / "web" / "themes" / "phantom.html"
OUT = ROOT / ".github" / "assets"

MOCK_DATA = {
    "speed": 287,
    "gear": 5,
    "rpm": 7420,
    "engine_max_rpm": 8500,
    "boost": 1.4,
    "fuel": 0.72,
    "power": 632,
    "torque": 718,
    "tires": {
        "FL": {"temp": 87, "combined_slip": 0.12},
        "FR": {"temp": 91, "combined_slip": 0.15},
        "RL": {"temp": 78, "combined_slip": 0.08},
        "RR": {"temp": 82, "combined_slip": 0.10},
    },
    "car_ordinal": "LAMBORGHINI AVENTADOR",
    "car_class": "S2",
    "car_perf": 998,
    "drivetrain": "AWD",
    "num_cylinders": 12,
    "lap_no": 3,
    "cur_lap_time": 72.456,
    "best_lap_time": 71.234,
    "last_lap_time": 72.891,
    "race_pos": 1,
    "dist_traveled": 8420,
    "accel_x": 0.35,
    "accel_z": -0.82,
    "position_x": 120.5,
    "position_y": -340.2,
    "speed_ms": 79.7,
}


def generate_track_points(n=800):
    """Generate track points forming a racing circuit shape."""
    points = []
    for i in range(n):
        t = 2 * math.pi * i / n
        # Oval circuit with chicanes
        x = 300 * math.cos(t) + 40 * math.cos(3 * t)
        y = 200 * math.sin(t) + 25 * math.sin(2 * t)
        # Brake at corners (where curvature is high)
        curvature = abs(math.sin(t)) * 100
        brake = -int(curvature) if curvature > 50 else 0
        # Driving line deviation — slight errors at corners
        dev = int(15 * math.sin(5 * t)) if curvature > 40 else 0
        points.append({
            "position_x": str(x),
            "position_y": str(y),
            "norm_driving_line": str(dev),
            "norm_ai_brake_diff": str(brake),
            "yaw": str(0.3 * math.cos(t)),
            "speed": str(80 - 30 * abs(math.sin(t))),
        })
    return points


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(f"file://{THEME}")
        page.wait_for_timeout(1000)

        # --- 1. Dashboard screenshot ---
        page.evaluate(f"updateDashboard({json.dumps(MOCK_DATA)})")
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / "dashboard.png"), full_page=False)
        print(f"Saved {OUT / 'dashboard.png'}")

        # --- 2. Torque analysis screenshot ---
        page.evaluate("_switchToAnalysis()")
        page.wait_for_timeout(300)
        page.evaluate("""
        var mockAnalysis = {
            gears: {
                1: {samples: [{rpm: 2000, trq: 400}, {rpm: 4000, trq: 620}, {rpm: 6000, trq: 710}, {rpm: 7500, trq: 680}]},
                2: {samples: [{rpm: 2000, trq: 380}, {rpm: 4000, trq: 590}, {rpm: 6000, trq: 680}, {rpm: 7500, trq: 640}]},
                3: {samples: [{rpm: 2000, trq: 350}, {rpm: 4000, trq: 560}, {rpm: 6000, trq: 650}, {rpm: 7500, trq: 600}]},
                4: {samples: [{rpm: 2000, trq: 320}, {rpm: 4000, trq: 520}, {rpm: 6000, trq: 610}, {rpm: 7500, trq: 560}]},
                5: {samples: [{rpm: 2000, trq: 290}, {rpm: 4000, trq: 480}, {rpm: 6000, trq: 560}, {rpm: 7500, trq: 510}]},
                6: {samples: [{rpm: 2000, trq: 260}, {rpm: 4000, trq: 430}, {rpm: 6000, trq: 500}, {rpm: 7500, trq: 450}]},
            },
            shiftPoints: {1:7200, 2:7100, 3:7000, 4:6900, 5:6800}
        };
        if (typeof updateChartsUI === 'function') updateChartsUI(mockAnalysis);
        if (typeof updateShiftPointsUI === 'function') updateShiftPointsUI(mockAnalysis);
        """)
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / "torque-analysis.png"), full_page=False)
        print(f"Saved {OUT / 'torque-analysis.png'}")

        # --- 3. Track map screenshot (live tab with track data) ---
        page.evaluate("""
        document.querySelectorAll('.tab-btn').forEach(function(b) { b.classList.remove('active'); });
        document.querySelectorAll('.tab-pane').forEach(function(p) { p.classList.remove('active'); });
        var btn = document.querySelector('.tab-btn[data-tab="live"]');
        var pane = document.getElementById('tab-live');
        if (btn) btn.classList.add('active');
        if (pane) pane.classList.add('active');
        """)
        page.wait_for_timeout(300)

        track_points = generate_track_points()
        # Push track data in batches via JS for speed
        batch_js = "var pts = " + json.dumps(track_points) + ";"
        batch_js += """
        for (var i = 0; i < pts.length; i++) {
            pushTrackData(pts[i]);
        }
        drawTrack();
        """
        page.evaluate(batch_js)
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / "track-map.png"), full_page=False)
        print(f"Saved {OUT / 'track-map.png'}")

        # --- 4. Coach HUD screenshot (same track + high tire slip) ---
        coach_data = dict(MOCK_DATA)
        coach_data["tires"] = {
            "FL": {"temp": 102, "combined_slip": 0.85},
            "FR": {"temp": 108, "combined_slip": 0.92},
            "RL": {"temp": 95, "combined_slip": 0.60},
            "RR": {"temp": 98, "combined_slip": 0.70},
        }
        coach_data["speed"] = 195
        coach_data["gear"] = 3
        coach_data["rpm"] = 6800
        page.evaluate(f"updateDashboard({json.dumps(coach_data)})")
        page.evaluate(batch_js)
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / "coach-hud.png"), full_page=False)
        print(f"Saved {OUT / 'coach-hud.png'}")

        browser.close()
        print("Done.")


if __name__ == "__main__":
    main()
