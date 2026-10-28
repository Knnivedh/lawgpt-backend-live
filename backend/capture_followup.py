import asyncio
from playwright.async_api import async_playwright

async def capture():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(viewport={'width': 1400, 'height': 950})
        page = await context.new_page()
        await page.goto('http://localhost:3000')
        await page.locator('.demo-account-card').first.click()
        await page.wait_for_timeout(2000)
        
        # Click question
        q_btn = page.locator("button:has-text('Husband Claims Business Loss')").first
        await q_btn.click()
        await page.wait_for_timeout(500)
        
        # Send
        await page.locator('button.query-send-btn').first.click()
        print('Query sent! Waiting for response stream...')
        
        # Wait up to 15s for response
        await page.wait_for_timeout(12000)
        
        # Screenshot
        await page.screenshot(path="C:/Users/LOQ/.gemini/antigravity/brain/2b0f4dd3-40cd-4014-8a58-4053543a6260/crosscheck_live_followup_question.png")
        print("Captured crosscheck_live_followup_question.png successfully!")
        await browser.close()

if __name__ == '__main__':
    asyncio.run(capture())
