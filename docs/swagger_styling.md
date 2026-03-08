# Swagger UI Styling Guide

This document outlines the strategy used to customize the Swagger UI for a dark theme and how to debug future styling issues.

## CSS Strategy

The custom styles are defined in `app/static/swagger.css`.

### key Principles

1.  **Inline Theme Variables:**
    To ensure variables like `--b1` (background) and `--bc` (text color) are always available, they are inlined at the top of `swagger.css` inside a `:root` block. This removes dependency on external `theme.css` loading order.

2.  **High Specificity & `!important`:**
    Swagger UI's default styles are very specific and often use `!important`. To override them effectively:
    *   We use high-specificity selectors like `html body .swagger-ui ...`.
    *   For **text contrast** (headers, descriptions, parameters), we use `!important` to force the light text color (`var(--bc)`). This is necessary because default Swagger UI styles often hardcode colors on specific elements like `h4`, `td`, and `label`.

3.  **JSON Schema 2020-12 Compatibility:**
    Newer Swagger UI versions use `json-schema-2020-12` components for the "Schemas" section. These have their own specific background rules that must be overridden to prevent white blocks.

### Cache Busting

Browsers aggressively cache CSS files. When you make changes to `swagger.css`, you **must** bump the version query parameter in `app/main_api.py`.

**File:** `app/main_api.py`
```python
swagger_css_url="/static/swagger.css?v=fixed6",  # Update this version string!
```

## Debugging with Playwright

If the browser agent is unable to inspect the DOM (e.g., due to environment issues), you can use a manual Playwright script to inspect computed styles.

**Prerequisites:**
```bash
poetry add --group dev playwright
poetry run playwright install chromium
```

**Debug Script (`debug_swag.py`):**
```python
import os
import asyncio
from playwright.async_api import async_playwright

# Fix environment for Windows if HOME/USERPROFILE is missing
if "HOME" not in os.environ:
    if "USERPROFILE" in os.environ:
        os.environ["HOME"] = os.environ["USERPROFILE"]

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto("http://localhost:8000/docs", wait_until="networkidle")
        
        # Example: Check computed color of a header
        header = await page.query_selector("section.models h4")
        if header:
            color = await header.evaluate("el => window.getComputedStyle(el).color")
            print(f"Header Color: {color}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
```

Run with: `poetry run python debug_swag.py`
