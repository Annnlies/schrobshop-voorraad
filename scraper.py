#!/usr/bin/env python3
"""
Schrobshop voorraad-guard
=========================
Leest dagelijks de voorraadstatus van producten op aukerauwerda.nl en schrijft
een voorraad.csv die WP All Import in WooCommerce inleest.

- Invoer : mapping.csv  (kolommen: woocommerce_sku, product, ar_url)
- Uitvoer: voorraad.csv (kolommen: sku, stock_status, prijs_excl_btw, gecontroleerd_op)

stock_status is 'instock' of 'outofstock' (exact de waarden die WooCommerce gebruikt).
Producten die niet gelezen konden worden, worden NIET weggeschreven, zodat WP All
Import ze met rust laat (liever overslaan dan per ongeluk op uitverkocht zetten).
"""

import csv
import sys
import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = Path(__file__).parent
MAPPING = BASE / "mapping.csv"
OUTPUT = BASE / "voorraad.csv"
TIMEOUT = 30000  # ms per pagina


def lees_status(page, url):
    """Open een AR-productpagina en bepaal voorraad + prijs. Retourneert (status, prijs) of (None, None)."""
    page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT)

    # Cookiebanner best-effort wegklikken (blokkeert anders soms de render)
    for tekst in ("Alle cookies weigeren", "Accepteer alle cookies"):
        try:
            knop = page.get_by_role("button", name=tekst)
            if knop.count():
                knop.first.click(timeout=2000)
                break
        except Exception:
            pass

    # 1) Betrouwbaarste signaal: schema.org availability
    status = None
    try:
        el = page.locator('[itemprop="availability"]').first
        if el.count():
            val = (el.get_attribute("href") or el.get_attribute("content") or "")
            if "InStock" in val:
                status = "instock"
            elif "OutOfStock" in val:
                status = "outofstock"
    except Exception:
        pass

    # 2) Fallback: aanwezigheid van een actieve 'In Winkelwagen'-knop
    if status is None:
        try:
            knop = page.locator("button.tocart, #product-addtocart-button").first
            if knop.count() and knop.is_enabled():
                status = "instock"
            else:
                status = "outofstock"
        except Exception:
            status = None

    # Prijs excl. btw (laagste getoonde prijs); puur informatief, mag leeg
    prijs = ""
    try:
        import re
        tekst = page.locator("body").inner_text()
        bedragen = re.findall(r"€\s*([0-9]+[.,][0-9]{2})", tekst)
        if bedragen:
            prijs = min(float(b.replace(".", "").replace(",", ".")) for b in bedragen)
            prijs = f"{prijs:.2f}"
    except Exception:
        pass

    return status, prijs


def main():
    if not MAPPING.exists():
        print(f"mapping.csv niet gevonden op {MAPPING}", file=sys.stderr)
        sys.exit(1)

    with open(MAPPING, newline="", encoding="utf-8") as f:
        rijen = [r for r in csv.DictReader(f) if r.get("ar_url", "").strip()]

    vandaag = datetime.date.today().isoformat()
    resultaten, mislukt = [], []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"))
        for r in rijen:
            sku = r["woocommerce_sku"].strip()
            url = r["ar_url"].strip()
            try:
                status, prijs = lees_status(page, url)
            except Exception as e:
                status, prijs = None, ""
                print(f"FOUT {sku} {url}: {e}", file=sys.stderr)
            if status:
                resultaten.append({"sku": sku, "stock_status": status,
                                   "prijs_excl_btw": prijs, "gecontroleerd_op": vandaag})
                print(f"OK   {sku:15} {status:10} €{prijs}")
            else:
                mislukt.append(sku)
                print(f"SKIP {sku:15} (status onbekend)")
        browser.close()

    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["sku", "stock_status", "prijs_excl_btw", "gecontroleerd_op"])
        w.writeheader()
        w.writerows(resultaten)

    print(f"\nKlaar: {len(resultaten)} geschreven, {len(mislukt)} overgeslagen -> {OUTPUT}")
    if mislukt:
        print("Overgeslagen SKU's:", ", ".join(mislukt))


if __name__ == "__main__":
    main()
