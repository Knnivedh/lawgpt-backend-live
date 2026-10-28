import asyncio
from playwright.async_api import async_playwright

async def inspect():
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
        await page.wait_for_timeout(10000)
        
        msgs = await page.locator('.family-msg').all_inner_texts()
        print(f'Total family-msg elements: {len(msgs)}')
        for i, m in enumerate(msgs):
            print(f'  Msg {i}: {repr(m[:180])}')

        # Check intake checklist
        intake_items = await page.locator('.intake-item, .widget-list-item').all_inner_texts()
        print(f'Total widgets/items: {len(intake_items)}')
        for item in intake_items[:5]:
            print(f'  Item: {repr(item[:80])}')

        await browser.close()

if __name__ == '__main__':
    asyncio.run(inspect())
