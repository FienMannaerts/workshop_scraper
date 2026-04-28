import asyncio
import os
import pandas as pd
from datetime import datetime
from playwright.async_api import async_playwright
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

rows = []

async def scrape():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for page_number in range(1, 75):
            url = f"https://www.breiwebshop.nl/wol-garen/?p={page_number}"
            await page.goto(url, wait_until="networkidle")

            items = await page.query_selector_all("li.PRB.PRBh")

            if not items:
                break

            for item in items:
                try:
                    title_node = await item.query_selector("a.PRBn")
                    full_title = await title_node.get_attribute("title") if title_node else None
                    if full_title and full_title.startswith("Bekijk: "):
                        full_title = full_title[8:]
                except:
                    full_title = None

                if full_title:
                    parts = full_title.split(" - ", 1)
                    brand = parts[0].strip()
                    product_name = parts[1].strip() if len(parts) > 1 else full_title
                else:
                    brand = None
                    product_name = None

                try:
                    price_node = await item.query_selector("span.PRI")
                    price_text = await price_node.inner_text() if price_node else None
                except:
                    price_text = None

                rows.append({
                    "brand": brand,
                    "product_name": product_name,
                    "full_title": full_title,
                    "price_text": price_text,
                })

            await asyncio.sleep(1)

    await browser.close()

await scrape()

df = pd.DataFrame(rows)

df["price"] = (
    df["price_text"]
      .str.replace(",", ".", regex=False)
      .str.replace(r"[^0-9.]", "", regex=True)
      .astype(float)
)

scrape_time = datetime.now().isoformat()

insert_rows = []
for _, row in df.iterrows():
    insert_rows.append({
        "brand":        str(row.get("brand", "")),
        "product_name": str(row.get("product_name", "")),
        "full_title":   str(row.get("full_title", "")),
        "price_text":   str(row.get("price_text", "")),
        "price_eur":    float(row.get("price") or 0),
        "scraped_at":   scrape_time,
    })

result = supabase.table("workshop_scraper").insert(insert_rows).execute()
print(f"✅ Inserted {len(insert_rows)} rows into Supabase")