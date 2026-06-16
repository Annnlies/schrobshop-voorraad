# Schrobshop voorraad-guard

Houdt je webshop automatisch gelijk met de voorraad van Auke Rauwerda, zodat je niets verkoopt wat daar niet leverbaar is.

**Hoe het werkt:** elke ochtend draait er op GitHub (gratis) een scraper die per product de voorraadstatus op aukerauwerda.nl leest en wegschrijft naar `voorraad.csv`. WP All Import in je WooCommerce leest dat bestand dagelijks en zet producten op "op voorraad" of "uitverkocht".

```
GitHub Actions (dagelijks)  ->  voorraad.csv (vaste URL)  ->  WP All Import  ->  WooCommerce
```

## Eenmalige setup (±20 min)

1. Maak een gratis account op github.com (als je dat nog niet hebt).
2. Maak een nieuwe **private repository**, bijv. `schrobshop-voorraad`.
3. Upload alle bestanden uit deze map (incl. de map `.github/workflows/`).
4. Ga in de repo naar **Settings → Actions → General** en zet werkende toestemming aan ("Read and write permissions").
5. Ga naar het tabblad **Actions** en draai de workflow "Voorraad scrapen" één keer handmatig (knop *Run workflow*) om te testen.
6. Na een geslaagde run staat `voorraad.csv` in de repo. De vaste URL is:
   `https://raw.githubusercontent.com/<jouw-gebruikersnaam>/schrobshop-voorraad/main/voorraad.csv`
7. Zet die URL in WP All Import — zie `WP-All-Import-instructies.md`.

Vanaf dan draait alles automatisch, elke ochtend.

## De koppeltabel (`mapping.csv`)

Dit bepaalt welke producten gecontroleerd worden. Kolommen:

| kolom | betekenis |
|-------|-----------|
| `woocommerce_sku` | het SKU zoals in jouw WooCommerce |
| `product` | naam (alleen voor jezelf) |
| `ar_url` | de exacte productpagina op aukerauwerda.nl |

Er staan nu 5 bevestigde producten in. De rest staat in `mapping-nog-aanvullen.csv`:
zoek het product op aukerauwerda.nl, kopieer de URL uit je adresbalk en plak hem
in de `ar_url`-kolom, en verplaats de regel naar `mapping.csv`. Meer regels = meer
producten bewaakt.

## Belangrijk

- **Veilig bij twijfel:** kan de scraper een product niet lezen, dan slaat hij het over (laat WooCommerce ongemoeid) in plaats van het per ongeluk op uitverkocht te zetten.
- **SKU-match:** WP All Import koppelt op SKU. Je WooCommerce-SKU's zijn de fabriekscodes; die hoeven niet gelijk te zijn aan Rauwerda's artikelnummers — de koppeling loopt via `mapping.csv`.
- **Onderhoud:** verandert Rauwerda een product-URL, dan moet die regel in `mapping.csv` bijgewerkt worden. Een overgeslagen product in de log wijst daarop.
