#!/usr/bin/env python3
"""
Schrobshop voorraad-guard
=========================
Leest dagelijks de voorraadstatus van producten op aukerauwerda.nl en schrijft
een voorraad.csv die WooCommerce (via Code Snippets) inleest.

- Invoer : mapping.csv  (kolommen: woocommerce_sku, product, ar_url)
- Uitvoer: voorraad.csv (kolommen: sku, stock_status, prijs_excl_btw, gecontroleerd_op)

Werkt voor simpele EN configureerbare (Vikan e.d.) producten.

PROXY (optioneel): als de omgevingsvariabelen PROXY_SERVER / PROXY_USERNAME /
PROXY_PASSWORD gezet zijn, gaat al het verkeer via een residential proxy. Dat is
nodig om de zwaardere Vikan-pagina's te kunnen lezen (Rauwerda blokkeert anders
datacenter-IP's). Zonder die variabelen draait hij gewoon zonder proxy.

Afbeeldingen/fonts/media worden geblokkeerd om dataverbruik (en proxy-kosten)
minimaal te houden.

VEILIG BIJ TWIJFEL: een product wordt alleen weggeschreven als de status met
zekerheid is vastgesteld; lukt het laden niet, dan wordt het OVERGESLAGEN i.p.v.
foutief op 'uitverkocht' gezet. Niet-gelezen producten krijgen een tweede ronde.
"""

import csv
import os
import sys
import time
import random
import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = Path(__file__).parent
MAPPING = BASE / "mapping.csv"
OUTPUT = BASE / "voorraad.csv"
TIMEOUT = 45000  # ms
POGINGEN = 3

STEALTH = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['nl-NL','nl','en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
window.chrome = window.chrome || {runtime: {}};
"""

BLOK = {"image", "media", "font", "stylesheet"}


def _proxy():
    server = os.environ.get("PROXY_SERVER", "").strip()
    if not server:
        return None
    p = {"server": server}
    u = os.environ.get("PROXY_USERNAME", "").strip()
    w = os.environ.get("PROXY_PASSWORD", "").strip()
    if u:
        p["username"] = u
    if w:
        p["password"] = w
    return p


def _dismiss_cookies(page):
    for tekst in ("Alle cookies weigeren", "Accepteer alle cookies", "Accepteer", "Weigeren"):
        try:
            knop = page.get_by_role("button", name=tekst)
            if knop.count():
                knop.first.click(timeout=2000)
                page.wait_for_timeout(400)
                return
        except Exception:
            pass


def _status(page):
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
    if any(t in body for t in ["niet op voorraad", "uitverkocht", "niet leverbaar", "tijdelijk niet leverbaar"]):
        return "outofstock"
    return None


def lees(page, url):
    for poging in range(1, POGINGEN + 1):
        try:
            wachten = "networkidle" if poging == 1 else "domcontentloaded"
            page.goto(url, wait_until=wachten, timeout=TIMEOUT)
            _dismiss_cookies(page)
            try:
                page.wait_for_selector("h1", timeout=15000)
            except Exception:
                page.wait_for_timeout(2000 + random.randint(0, 1500))
                continue
            try:
                page.wait_for_selector('[itemprop="availability"], button.tocart', timeout=8000)
            except Exception:
                page.wait_for_timeout(1500)
            status = _status(page)
            if status:
                prijs = ""
                try:
                    import re
                    bedragen = re.findall(r"€\s*([0-9]+[.,][0-9]{2})", page.locator("body").inner_text())
                    if bedragen:
                        prijs = f"{min(float(b.replace('.', '').replace(',', '.')) for b in bedragen):.2f}"
                except Exception:
                    pass
                return status, prijs
        except Exception as e:
            print(f"  poging {poging} fout: {e}", file=sys.stderr)
        page.wait_for_timeout(2000 + random.randint(0, 2000))
    return None, ""


def main():
    if not MAPPING.exists():
        print(f"mapping.csv niet gevonden op {MAPPING}", file=sys.stderr)
        sys.exit(1)

    with open(MAPPING, newline="", encoding="utf-8") as f:
        rijen = [r for r in csv.DictReader(f) if r.get("ar_url", "").strip()]

    vandaag = datetime.date.today().isoformat()
    resultaten, mislukt = {}, []
    proxy = _proxy()
    print("Proxy actief" if proxy else "Geen proxy (datacenter-IP)")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, proxy=proxy,
                                    args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(
            locale="nl-NL",
            user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
            viewport={"width": 1366, "height": 900},
            extra_http_headers={"Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8"},
        )
        ctx.add_init_script(STEALTH)
        ctx.route("**/*", lambda route: route.abort()
                  if route.request.resource_type in BLOK else route.continue_())
        page = ctx.new_page()

        def verwerk(rij):
            sku = rij["woocommerce_sku"].strip()
            url = rij["ar_url"].strip()
            status, prijs = lees(page, url)
            if status:
                resultaten[sku] = {"sku": sku, "stock_status": status,
                                   "prijs_excl_btw": prijs, "gecontroleerd_op": vandaag}
                print(f"OK   {sku:15} {status:10} EUR{prijs}")
                return True
            print(f"SKIP {sku:15} (status onbekend)")
            return False

        for rij in rijen:
            if not verwerk(rij):
                mislukt.append(rij)
            page.wait_for_timeout(1200 + random.randint(0, 1800))

        if mislukt:
            print(f"\nTweede ronde voor {len(mislukt)} overgeslagen producten...")
            time.sleep(5)
            rest = []
            for rij in mislukt:
                if not verwerk(rij):
                    rest.append(rij["woocommerce_sku"].strip())
                page.wait_for_timeout(1500 + random.randint(0, 2000))
            mislukt = rest

        browser.close()

    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["sku", "stock_status", "prijs_excl_btw", "gecontroleerd_op"])
        w.writeheader()
        w.writerows(resultaten.values())

    print(f"\nKlaar: {len(resultaten)} geschreven, {len(mislukt) if isinstance(mislukt, list) else 0} overgeslagen -> {OUTPUT}")
    if mislukt:
        print("Overgeslagen SKU's:", ", ".join(mislukt))


if __name__ == "__main__":
    main()
