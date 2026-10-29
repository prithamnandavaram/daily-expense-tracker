"""
take_screenshots.py — Capture crystal-clear screenshots of the application.
"""

import os
import time
from playwright.sync_api import sync_playwright

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
OUT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(OUT_DIR, exist_ok=True)

BASE_URL = "http://127.0.0.1:5050"


def capture():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME_PATH, headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 920},
            device_scale_factor=2,  # Retina high-DPI quality
        )
        page = context.new_page()

        # 1. Login Page
        print("Capturing 01_login.png...")
        page.goto(f"{BASE_URL}/login")
        page.wait_for_timeout(1000)
        page.screenshot(path=os.path.join(OUT_DIR, "01_login.png"))

        # 2. Main Dashboard (Questions a, d, b)
        print("Capturing 02_dashboard_overview.png...")
        page.goto(f"{BASE_URL}/?demo_user=admin")
        page.wait_for_timeout(2500)  # Allow Chart.js animations to settle
        page.screenshot(path=os.path.join(OUT_DIR, "02_dashboard_overview.png"))

        # 3. Full-page Dashboard
        print("Capturing 03_dashboard_full.png...")
        page.screenshot(path=os.path.join(OUT_DIR, "03_dashboard_full.png"), full_page=True)

        # 4. Global Analytics Section (Questions c, e, f, g)
        print("Capturing 04_analytics_scenarios.png...")
        page.evaluate("window.scrollTo(0, 750)")
        page.wait_for_timeout(1000)
        page.screenshot(path=os.path.join(OUT_DIR, "04_analytics_scenarios.png"))

        # 5. Interactive Movie Search & Rating Modification
        print("Capturing 05_movie_interaction.png...")
        page.goto(f"{BASE_URL}/?demo_user=user")
        page.wait_for_timeout(1500)
        search_input = page.locator("#movieSearch")
        search_input.fill("Matrix")
        page.wait_for_timeout(800)
        matrix_item = page.locator('.search-item:has-text("The Matrix")').first
        if matrix_item.count() > 0:
            matrix_item.click()
            page.wait_for_timeout(1500)
            page.screenshot(path=os.path.join(OUT_DIR, "05_movie_interaction.png"))

        # 6. Presentation Slides (Deliverable 1)
        print("Capturing 06_presentation_slides.png...")
        page.goto(f"{BASE_URL}/slides?demo_user=admin")
        page.wait_for_timeout(1500)
        page.screenshot(path=os.path.join(OUT_DIR, "06_presentation_slides.png"))

        # 7. Administrator Console
        print("Capturing 07_admin_console.png...")
        page.goto(f"{BASE_URL}/admin?demo_user=admin")
        page.wait_for_timeout(1500)
        page.screenshot(path=os.path.join(OUT_DIR, "07_admin_console.png"))

        browser.close()
        print("✨ All screenshots successfully captured to ./screenshots directory!")


if __name__ == "__main__":
    capture()
