import asyncio
import io
import zipfile
import os
import time
from playwright.async_api import async_playwright

def create_temp_zip():
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("app/api/endpoints.py", """from fastapi import FastAPI
app = FastAPI()
@app.get("/")
def read_root():
    eval("arbitrary_string")
""")
        zf.writestr("app/auth/login.py", """# Authentication helper
def perform_login():
    try:
        pass
    except Exception:
        pass
""")
        zf.writestr("app/utils/helpers.py", """# Utility helper
def run_helper():
    pass
""")
        zf.writestr("vendor/library.js", """console.log("vendor library contents");""")
    return zip_buffer.getvalue()

async def main():
    # Save a temporary zip file to upload
    zip_data = create_temp_zip()
    zip_name = "pipeline_test.zip"
    with open(zip_name, "wb") as f:
        f.write(zip_data)
        
    async with async_playwright() as p:
        # Launch browser
        print("Launching browser...")
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await context.new_page()
        
        # Navigate to application
        print("Navigating to http://127.0.0.1:8000...")
        await page.goto("http://127.0.0.1:8000")
        await page.wait_for_timeout(1000)
        
        # Sign up
        print("Registering walkthrough user...")
        await page.click("#tab-signup-btn")
        timestamp = int(time.time())
        username = f"walkthrough_user_{timestamp}"
        await page.fill("#auth-username", username)
        await page.fill("#auth-password", "securepassword123")
        await page.select_option("#auth-role", "user")
        await page.click("#btn-auth-submit")
        await page.wait_for_timeout(1500)
        
        # Log in
        print("Logging in...")
        await page.click("#tab-login-btn")
        await page.fill("#auth-username", username)
        await page.fill("#auth-password", "securepassword123")
        await page.click("#btn-auth-submit")
        await page.wait_for_timeout(1500)
        
        # Go to projects
        print("Navigating to Projects tab on sidebar...")
        await page.click("button[data-view='view-projects']")
        await page.wait_for_timeout(1000)
        
        # Create Project
        print("Opening create project modal...")
        await page.click("#btn-create-project-modal")
        await page.wait_for_timeout(500)
        await page.fill("#project-modal-name", "FastAPI Review Pipeline Demo")
        await page.click('#project-create-form button[type="submit"]')
        await page.wait_for_timeout(2000)
        
        # Upload zip
        print("Selecting ZIP ingestion tab...")
        await page.click('.ingestion-tabs button[data-tab="ingest-zip"]')
        await page.wait_for_timeout(500)
        
        print("Uploading codebase ZIP...")
        file_input = page.locator("#zip-file-input")
        await file_input.set_input_files(zip_name)
        await page.wait_for_timeout(1000)
        
        # Handle dialogs (automatically accept alerts)
        page.on("dialog", lambda dialog: asyncio.create_task(dialog.accept()))
        
        print("Clicking Ingest ZIP...")
        await page.click("#btn-ingest-zip")
        await page.wait_for_timeout(3000)
        
        # Run AI Review
        print("Triggering AI Review Pipeline...")
        await page.click("#btn-start-project-analysis")
        await page.wait_for_timeout(1500)
        
        # Capture screenshot while the pipeline is running (to show the running stage with purple/teal dot!)
        print("Capturing screenshot of running pipeline...")
        running_screenshot_path = "C:\\Users\\datta\\.gemini\\antigravity-ide\\brain\\be0a1196-2e3d-418c-a10a-381601e1a284\\pipeline_running_screenshot.png"
        await page.screenshot(path=running_screenshot_path, full_page=False)
        print(f"Running screenshot successfully saved to: {running_screenshot_path}")
        
        # Wait for the analysis pipeline run to finish (waiting for report card to show)
        print("Waiting for review pipeline to complete and report card to appear...")
        await page.wait_for_selector("#project-report-card", state="visible", timeout=30000)
        await page.wait_for_timeout(2000)
        
        # Capture screenshot of completed report and telemetry card
        print("Capturing dashboard report screenshot...")
        screenshot_path = "C:\\Users\\datta\\.gemini\\antigravity-ide\\brain\\be0a1196-2e3d-418c-a10a-381601e1a284\\pipeline_completed_screenshot.png"
        await page.screenshot(path=screenshot_path, full_page=False)
        print(f"Completed screenshot successfully saved to: {screenshot_path}")
        
        # Clean up temporary zip file
        if os.path.exists(zip_name):
            os.remove(zip_name)
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
