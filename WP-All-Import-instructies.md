# WP All Import instellen voor de voorraad-guard

Doel: WooCommerce leest dagelijks `voorraad.csv` en zet producten op "op voorraad" of "uitverkocht".

Nodig: de plugins **WP All Import** en **WooCommerce Import Add-On** (gratis versies volstaan voor stockupdates; inplannen zit in de Pro-versie — zie stap 7 voor een gratis alternatief).

## Stappen

1. **WordPress → All Import → New Import.**
2. Kies **"Download from URL"** en plak je vaste CSV-URL:
   `https://raw.githubusercontent.com/<gebruikersnaam>/schrobshop-voorraad/main/voorraad.csv`
3. Kies **"Existing Items"** → **WooCommerce Products** (je werkt bestaande producten bij, je maakt niets nieuws aan).
4. **Matchen op SKU:** in de stap "Record matching" / "Unique identifier" kies je het veld `sku` uit het bestand en koppel je dat aan het WooCommerce-SKU. Zo weet de import welk product bij welke regel hoort.
5. **Velden bijwerken:** zet de import zó dat alleen de voorraadstatus wordt aangepast:
   - **Stock Status** = de kolom `stock_status` (waarden `instock` / `outofstock` sluiten exact aan op WooCommerce).
   - Bij "Which data to update": vink **alleen** "Stock" / "Inventory" aan en laat titel, prijs, beschrijving e.d. uit. (Tip: prijs staat als bonus in de kolom `prijs_excl_btw`; alleen koppelen als je dat bewust wilt.)
6. Rond de import af en draai hem één keer om te testen. Controleer of een paar producten de juiste status krijgen.
7. **Automatisch dagelijks laten lopen — twee opties:**
   - **Gratis:** WP All Import geeft onder "Manage Imports" een **trigger-URL** en **processing-URL**. Laat een gratis dienst als cron-job.org die twee URL's elke ochtend aanroepen. Of plak de trigger-URL in `.github/workflows/daily.yml` (onderaan, regel met `curl`), dan importeert WordPress meteen na elke scrape.
   - **Betaald:** WP All Import Pro heeft een ingebouwde "Scheduling"-optie (dagelijks).

## Controle

- Draait de GitHub-scraper 's ochtends, daarna de import → je shop loopt elke dag automatisch mee met Rauwerda.
- Zie je een product onterecht op uitverkocht? Check de `ar_url` van dat product in `mapping.csv` (URL mogelijk gewijzigd).
