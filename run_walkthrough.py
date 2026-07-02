import asyncio
from playwright.async_api import async_playwright
import os

async def main():
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Navigate
        print("Navigating to http://127.0.0.1:8000...")
        await page.goto("http://127.0.0.1:8000")
        await page.wait_for_timeout(1000)
        
        # Click Sign Up tab
        print("Clicking Sign Up tab...")
        await page.click("#tab-signup-btn")
        
        # Fill signup fields
        print("Filling registration form...")
        await page.fill("#auth-username", "walkthrough_user")
        await page.fill("#auth-password", "securepassword123")
        await page.select_option("#auth-role", "user")
        
        # Submit registration
        print("Submitting registration...")
        await page.click("#btn-auth-submit")
        await page.wait_for_timeout(2000)
        
        # Click Login tab just in case
        print("Logging in...")
        await page.click("#tab-login-btn")
        await page.fill("#auth-username", "walkthrough_user")
        await page.fill("#auth-password", "securepassword123")
        await page.click("#btn-auth-submit")
        await page.wait_for_timeout(2000)
        
        # Navigate to Projects tab on sidebar
        print("Navigating to Projects tab on sidebar...")
        await page.click("button[data-view='view-projects']")
        await page.wait_for_timeout(1000)
        
        # Click + New Project
        print("Opening create project modal...")
        await page.click("#btn-create-project-modal")
        await page.wait_for_timeout(500)
        
        # Fill project name
        print("Filling project name...")
        await page.fill("#project-modal-name", "FastAPI Dashboard Demo")
        await page.click('#project-create-form button[type="submit"]')
        await page.wait_for_timeout(2000)
        
        # Click Upload ZIP Tab
        print("Selecting ZIP ingestion tab...")
        await page.click('.ingestion-tabs button[data-tab="ingest-zip"]')
        await page.wait_for_timeout(500)
        
        # Select file input
        print("Uploading fastapi_test.zip...")
        file_input = page.locator("#zip-file-input")
        await file_input.set_input_files("fastapi_test.zip")
        await page.wait_for_timeout(1000)
        
        # Set up dialog handler to automatically accept alerts
        page.on("dialog", lambda dialog: asyncio.create_task(dialog.accept()))
        
        # Click Ingest ZIP
        print("Clicking Ingest ZIP...")
        await page.click("#btn-ingest-zip")
        await page.wait_for_timeout(3000)
        
        # Take a beautiful screenshot of the active project view with Code Intelligence card visible
        print("Capturing dashboard screenshot...")
        screenshot_path = "C:\\Users\\datta\\.gemini\\antigravity-ide\\brain\\be0a1196-2e3d-418c-a10a-381601e1a284\\code_intelligence_screenshot.png"
        await page.screenshot(path=screenshot_path, full_page=False)
        print(f"Screenshot successfully saved to: {screenshot_path}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
