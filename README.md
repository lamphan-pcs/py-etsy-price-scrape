# Etsy Shop Scraper

A Python script using Playwright to scrape product prices and details from an Etsy shop, handling pagination and variations.

## Setup

1.  **Environment**: The repository uses a virtual environment `venv`.
    ```powershell
    python -m venv venv
    .\venv\Scripts\Activate.ps1
    ```
2.  **Dependencies**:
    ```powershell
    pip install -r requirements.txt
    playwright install chromium
    ```

## Usage

1.  **Configure URL**: Open `scraper.py` and change the `shop_url` variable at the bottom if needed.
    ```python
    shop_url = "https://www.etsy.com/shop/YourShopName"
    ```
2.  **Run**:
    ```powershell
    python scraper.py
    ```
    Or use the VS Code Task: "Run Etsy Scraper" (Ctrl+Shift+P > Tasks: Run Task).

## Captcha Handling

Etsy uses strong bot protection (DataDome). The script runs in partial "headed" mode (visible browser).
- If a CAPTCHA appears, **solve it manually in the browser window**.
- The script detects the CAPTCHA and waits for you to solve it.
- Once the page loads the products, the script will automatically continue.

## Output

The script generates `etsy_products.csv` containing:
- URL
- Title
- Base Price
- Variations info
