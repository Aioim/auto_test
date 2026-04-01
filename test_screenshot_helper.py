from playwright.sync_api import sync_playwright
from src.utils.common.screenshot_helper import ScreenshotHelper

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    try:
        helper = ScreenshotHelper(page)
        print("ScreenshotHelper initialized successfully")
    finally:
        browser.close()