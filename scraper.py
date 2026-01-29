import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import random
import json
import re

# Global timeout configuration
TIMEOUT = 0 # No timeout for navigation in case of captcha

async def scrape_etsy_shop(shop_url):
    all_product_urls = set()
    products_data = []
    
    async with async_playwright() as p:
        # Launch options - headless=False is required for manual captcha solving
        # specific args to try and hide automation
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
            ]
        ) 
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
            locale="en-US",
            timezone_id="America/New_York",
            permissions=["geolocation"]
        )
        
        # Evasion: Remove navigator.webdriver property
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        page = await context.new_page()
        
        # 1. Collect all Product URLs
        page_num = 1
        has_next_page = True
        
        # Initial navigation - might trigger Captcha
        print(f"Navigating to {shop_url}...")
        try:
            await page.goto(f"{shop_url}?ref=items_pagination&page=1", timeout=60000, wait_until="domcontentloaded")
        except Exception as e:
            print(f"Navigation warning: {e}")

        # specific check for captcha
        if "captcha" in page.url or await page.locator("iframe[src*='captcha']").count() > 0:
            print("CAPTCHA detected! Please solve it in the browser window.")
            print("The script will continue automatically once it detects listing items.")
        
        while has_next_page:
            current_url = f"{shop_url}?ref=items_pagination&page={page_num}"
            if page_num > 1:
                print(f"Scraping page {page_num}: {current_url}")
                await page.goto(current_url, timeout=60000, wait_until="domcontentloaded")

            # Wait for listings (long timeout to allow manual captcha solving)
            try:
                # Wait up to 5 minutes for user to solve captcha if needed
                await page.wait_for_selector('a.listing-link, a.v2-listing-card__link', timeout=300000)
            except:
                print(f"No listings found on page {page_num} after timeout. Ending pagination.")
                break

            # Get product data from list items directly
            
            # Usually the container is div.js-merch-stash-check-listing or li.wt-list-inline__item
            # We need to iterate over the containers to get matching URL and Price together
            
            product_cards = await page.locator('div.js-merch-stash-check-listing, li.wt-list-inline__item .v2-listing-card').all()
            
            if not product_cards:
                 # Fallback for new grid style
                 product_cards = await page.locator('a.listing-link').all()

            for card in product_cards:
                try:
                    # Get URL
                    if await card.count() == 0: continue
                    
                    # If card is describing the 'a' tag itself
                    tag_name = await card.evaluate("el => el.tagName")
                    if tag_name == "A":
                        link_el = card
                    else:
                        link_el = card.locator('a').first

                    url = await link_el.get_attribute('href')
                    if not url: continue
                    clean_url = url.split('?')[0]
                    
                    if clean_url in all_product_urls:
                        continue # Already scraped/seen
                    
                    all_product_urls.add(clean_url)
                    
                    # Title
                    title = "Unknown"
                    title_el = card.locator('h3, .v2-listing-card__title').first
                    if await title_el.count() > 0:
                        title = await title_el.text_content()
                        title = title.strip()
                    
                    # Price Info
                    price_text = ""
                    # Regular price
                    currency_el = card.locator('.currency-symbol').first
                    value_el = card.locator('.currency-value').first
                    
                    if await value_el.count() > 0:
                        price_text = await value_el.text_content()
                    
                    # Check for discount
                    # Sometimes structure is: <span class="wt-text-caption">Original Price</span> <span class="n-listing-card__price">Discounted</span>
                    # Just grab all text in price area
                    
                    price_area = card.locator('.n-listing-card__price, .v2-listing-card__info div p').first
                    if await price_area.count() > 0:
                        raw_price = await price_area.inner_text()
                        raw_price = raw_price.replace("\n", " ")
                    else:
                        raw_price = price_text
                        
                    products_data.append({
                        "url": clean_url,
                        "title": title,
                        "price_display": raw_price
                    })

                except Exception as e:
                    pass

            
            print(f"Found {len(product_cards)} cards. Total products collected: {len(products_data)}")
            
            if len(product_cards) < 36:
                print("Reached last page (less than 36 items).")
                break
            
            page_num += 1
            await asyncio.sleep(random.uniform(1.5, 3.5))

        await browser.close()
    
    return products_data

if __name__ == "__main__":
    shop_url = "https://www.etsy.com/shop/RubyVibeCo" 
    data = asyncio.run(scrape_etsy_shop(shop_url))
    
    # Save to CSV
    df = pd.DataFrame(data)
    df.to_csv("etsy_products.csv", index=False)
    print("Saved data to etsy_products.csv")


