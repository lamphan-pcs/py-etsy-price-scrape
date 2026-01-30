import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import random
import json
import re
import os
from datetime import datetime

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

        # Allow manual adjustment / Captcha solving
        print("-" * 50)
        print("PAUSED: Please solve any CAPTCHA in the browser now.")
        input("Press Enter in this terminal when CAPTCHA is solved to run auto-setup...")
        print("-" * 50)

        # Auto-set Locale/Currency
        try:
            print("Checking locale settings...")
            footer_btn = page.locator("#locale-picker-trigger")
            if await footer_btn.count() > 0:
                txt = await footer_btn.text_content()
                aria = await footer_btn.get_attribute("aria-label")
                current_info = (txt or "") + (aria or "")
                
                if "United States" in current_info and "USD" in current_info:
                    print("Settings already appear to be US / USD. Skipping update.")
                else:
                    print("Setting locale to United States / USD...")
                    await footer_btn.click()
                    
                    # Wait for overlay
                    await page.wait_for_selector("#locale-overlay-select-region_code", state="visible")
                    
                    # Select Region US
                    await page.select_option("#locale-overlay-select-region_code", "US")
                    
                    # Select Currency USD
                    await page.select_option("#locale-overlay-select-currency_code", "USD")
                    
                    # Click Save
                    await page.click("#locale-overlay-save")
                    
                    # Wait for page reload
                    await page.wait_for_load_state("domcontentloaded")
                    print("Successfully updated settings to US/USD.")
                    
                    # Small pause to ensure products reload
                    await asyncio.sleep(2)
        except Exception as e:
             print(f"Auto-setup warning: {e}")
        
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
                        title = title.strip().replace('â€“', '–')
                    
                    # Price Info
                    price_text = ""
                    # Regular price
                    currency_el = card.locator('.currency-symbol').first
                    value_el = card.locator('.currency-value').first
                    
                    if await value_el.count() > 0:
                        symbol = await currency_el.text_content() if await currency_el.count() > 0 else ""
                        price_text = symbol + await value_el.text_content()
                    
                    # Check for discount
                    # Sometimes structure is: <span class="wt-text-caption">Original Price</span> <span class="n-listing-card__price">Discounted</span>
                    # Just grab all text in price area
                    
                    price_area = card.locator('.n-listing-card__price, .v2-listing-card__info div p').first
                    if await price_area.count() > 0:
                        raw_price = await price_area.inner_text()
                        raw_price = raw_price.replace("\n", " ")
                    else:
                        raw_price = price_text
                    
                    # Derived Columns D and E
                    # D: First price match (Sale or Regular)
                    match_d = re.search(r"\$(\d+(?:\.\d{1,2})?)", raw_price)
                    val_d = match_d.group(1) if match_d else ""
                    
                    # E: Original Price if found, else D
                    match_e = re.search(r"Original Price[^$]*\$(\d+(?:\.\d{1,2})?)", raw_price)
                    if match_e:
                        val_e = match_e.group(1)
                    else:
                        val_e = val_d

                    products_data.append({
                        "url": clean_url,
                        "title": title,
                        "price_display": raw_price,
                        "current_price": val_d,
                        "original_price": val_e
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
    # Load configuration
    config_path = "config.json"
    shop_url = ""
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
                shop_url = config.get("shop_url", "").strip()
        except:
            pass
            
    if not shop_url:
        print("No shop_url found in config.json.")
        shop_url = input("Please enter the Etsy Shop URL: ").strip()
    
    if not shop_url:
        print("No URL provided. Exiting.")
        exit()

    print(f"Target Shop: {shop_url}")
    data = asyncio.run(scrape_etsy_shop(shop_url))
    
    # Save to CSV
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
    filename = f"etsy_products_{timestamp}.csv"
    filepath = os.path.join(output_dir, filename)
    
    df = pd.DataFrame(data)
    # Use utf-8-sig to ensure Excel opens the file correctly with special characters
    df.to_csv(filepath, index=False, encoding='utf-8-sig')
    print(f"Saved data to {filepath}")

    # Copy to clipboard
    try:
        df.to_clipboard(sep='\t', index=False)
        print("-" * 50)
        print("SUCCESS: Data copied to clipboard!")
        print("You can now pasting directly into Google Sheets or Excel (Ctrl+V).")
        print("-" * 50)
    except Exception as e:
        print(f"Clipboard copy failed: {e}")

    input("Press Enter to quit...")


