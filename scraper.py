#!/usr/bin/env python3
"""
Schrobshop voorraad-guard
=========================
Leest dagelijks de voorraadstatus van producten op aukerauwerda.nl en schrijft
een voorraad.csv die WP All Import in WooCommerce inleest.

- Invoer : mapping.csv  (kolommen: woocommerce_sku, product, ar_url)
- Uitvoer: voorraad.csv (kolommen: sku, stock_status, prijs_excl_btw, gecontroleerd_op)

VEILIG BIJ TWIJFEL: een product wordt alleen weggeschreven als de status met
zekerheid is vastgesteld. Laadt de pagina niet of is de status onduidelijk, dan
wordt het product OVERGESLAGEN (WooCommerce blijft ongemoeid) i.p.v. per ongeluk
op 'uitverkocht' gezet.
"""

import csv
import sys
import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = Path(__file__).parent
MAPPING = BASE / "mapping.csv"
OUTPUT = BASE / "voorraad.csv"
TIMEOUT = 45000  # ms


def _dismiss_cookies(page):
    for tekst in ("Alle cookies weigeren", "Accepteer alle cookies", "Accepteer", "Weigeren"):
        try:
            knop = page.get_by_role("button", name=tekst)
            if knop.count():
                knop.first.click(timeout=2000)
                page.wait_for_timeout(500)
                return
        except Exception:
            pass


def _bepaal_status(page):
    """Bepaal status op een geladen productpagina. Retourneert 'instock'/'outofstock'/None."""
    # 1) schema.org availability (betrouwbaarst)
    try:
        el = page.locator('[itemprop="availability"]').first
        if el.count():
            val = (el.get_attribute("href") or el.get_attribute("content") or "")
            if "InStock" in val:
                return "instock"
            if "OutOfStock" in val:
                return "outofstock"
    except Exception:
        pass
    # 2) positieve in-stock indicatoren
    try:
        if page.locator("button.tocart, #product-addtocart-button").first.is_enabled(timeout=2000):
            return "instock"
    except Exception:
        pass
    try:
        body = page.locator("body").inner_text().lower()
    except Exception:
        body = ""
    if "direct leverbaar" in body:
        return "instock"
    # 3) expliciete uitverkocht-tekst
    if any(t in body for t in ["niet op voorraad", "uitverkocht", "niet leverbaar", "tijdelijk niet leverbaar"]):
        return "outofstock"
    # 4) onbekend -> overslaan
    return None


def lees(page, url):
    """Open een AR-productpagina (met 1 retry) en bepaal status + prijs."""
    for poging in (1, 2):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT)
            _dismiss_cookies(page)
            # wacht tot de echte productpagina geladen is
            try:
                page.wait_for_selector("h1", timeout=15000)
            except Exception:
                continue  # pagina niet geladen -> retry
            # geef availability/JS even de tijd
            try:
                page.wait_for_selector('[itemprop="availability"], button.tocart', timeout=8000)
            except Exception:
                page.wait_for_timeout(1500)
            status = _bepaal_status(page)
            if status:
                prijs = ""
                try:
                    import re
                    tekst = page.locator("body").inner_text()
                    bedragen = re.findall(r"€\s*([0-9]+[.,][0-9]{2})", tekst)
                    if bedragen:
                        laagste = min(float(b.replace(".", "").replace(",", ".")) for b in bedragen)
                        prijs = f"{laagste:.2f}"
                except Exception:
                    pass
                return status, prijs
        except Exception as e:
            print(f"  poging {poging} fout: {e}", file=sys.stderr)
        page.wait_for_timeout(2000)
    return None, ""


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
        ctx = browser.new_context(
            locale="nl-NL",
            user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.new_page()
        for r in rijen:
            sku = r["woocommerce_sku"].strip()
            url = r["ar_url"].strip()
            status, prijs = lees(page, url)
            if status:
                resultaten.append({"sku": sku, "stock_status": status,
                                   "prijs_excl_btw": prijs, "gecontroleerd_op": vandaag})
                print(f"OK   {sku:15} {status:10} EUR{prijs}")
            else:
                mislukt.append(sku)
                print(f"SKIP {sku:15} (status onbekend - overgeslagen)")
            page.wait_for_timeout(1500)
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
