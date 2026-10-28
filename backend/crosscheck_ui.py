import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1400, "height": 950})
        page = await context.new_page()

        print("Navigating to http://localhost:3000 ...")
        await page.goto("http://localhost:3000", wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # 1. Click Instant Demo Profile
        demo_card = page.locator(".demo-account-card").first
        if await demo_card.is_visible():
            print("Clicking Instant Demo Profile (Adv. Rajesh Sharma)...")
            await demo_card.click()
            await page.wait_for_timeout(3000)

        # 2. Capture Dashboard
        print("Capturing Dashboard...")
        await page.screenshot(path="C:/Users/LOQ/.gemini/antigravity/brain/2b0f4dd3-40cd-4014-8a58-4053543a6260/crosscheck_1_dashboard.png", full_page=False)

        # 3. Click a question from Category 1
        q_btn = page.locator("button:has-text('Husband Claims Business Loss')").first
        if await q_btn.is_visible():
            print("Clicking 'Husband Claims Business Loss' question...")
            await q_btn.click()
            await page.wait_for_timeout(1000)

        # Capture with query filled in
        await page.screenshot(path="C:/Users/LOQ/.gemini/antigravity/brain/2b0f4dd3-40cd-4014-8a58-4053543a6260/crosscheck_2_query_filled.png", full_page=False)

        # 4. Click Submit button (.query-send-btn)
        send_btn = page.locator("button.query-send-btn").first
        print(f"Send button visible: {await send_btn.is_visible()}")
        if await send_btn.is_visible():
            print("Clicking Send button...")
            await send_btn.click()

            # Wait for response to populate
            print("Waiting for response...")
            try:
                await page.wait_for_selector(".family-msg-assistant, .results-tabs-nav, .results-panel-wrapper, .layman-summary-card", timeout=35000)
                await page.wait_for_timeout(6000)
            except Exception as e:
                print(f"Wait timeout or error: {e}")

            # Capture results view
            print("Capturing Result View...")
            await page.screenshot(path="C:/Users/LOQ/.gemini/antigravity/brain/2b0f4dd3-40cd-4014-8a58-4053543a6260/crosscheck_3_results.png", full_page=False)

        await browser.close()
        print("Playwright cross-check completed successfully!")

if __name__ == "__main__":
    asyncio.run(run())
