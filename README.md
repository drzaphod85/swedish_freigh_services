# Frakttjänster för Odoo 19

Sex samverkande moduler som integrerar Odoo 19 mot tre svenska
frakt-aggregatorer: **Fraktjakt**, **nShift Ship** (tidigare Unifaun)
och **Sendify**.

## Modulöversikt

| Modul | Roll | Beroenden |
|-------|------|-----------|
| `delivery_shipping_base` | Bas: gemensam API-klient (`ShippingClient`), produktfält (TARIC, ursprungsland, mått, farligt gods), `shipping.api.log` och statussekvens på pickings. | `delivery`, `stock` |
| `delivery_fraktjakt` | Fraktjakt XML-API v4.10 (Query, Order, Shipment, Track, Documents, Service Point, Webshops). Webhook-mottagare. | `delivery_shipping_base`, `sale_management`, `mail` |
| `delivery_fraktjakt_portal` | Spårning + statushistorik + ombudsväljare i kundportalen och website_sale-checkouten. | `delivery_fraktjakt`, `portal`, `website_sale` |
| `delivery_fraktjakt_returns` | Kund-initierad retur från portalen via Fraktjakts return_link. | `delivery_fraktjakt_portal` |
| `delivery_nshift` | nShift Ship REST-API. Rate, shipment, PDF-etikett. HTTP Basic-auth. | `delivery_shipping_base`, `sale_management`, `mail` |
| `delivery_sendify` | Sendify REST-API. Quote, booking, label. Bearer API-key. | `delivery_shipping_base`, `sale_management`, `mail` |

## Installationsordning

1. Lägg modulmapparna i Odoos `addons_path`.
2. Starta om Odoo med `-u all` (eller Apps → Update Apps List).
3. Installera **Shipping Base** (basen).
4. Installera de fraktbolag du använder — Fraktjakt, nShift, Sendify (en, två, eller alla).
5. Lägg till portal- och retur-modulerna om du har Fraktjakt + e-handel.

## Konfiguration

### Fraktjakt
- **Lager → Fraktjakt → Registrera nytt konto** för att klistra in eller skapa credentials.
- Webhook: `https://<din-odoo>/fraktjakt/webhook/<token>` klistras in i Fraktjakts integrationsinställningar.
- API-täckning: Query, Order Typ 1, Shipment, Track & Trace, Shipping Documents (Base64), Service Point Locator/Selector, Status, Shipping Products, Webshops + webhook-mottagare.

### nShift
- **Inställningar → Lager → nShift Ship**: Developer ID, Developer Key (lösenord), Customer No, Mode (test/prod), Service ID (frivilligt).
- Anpassa fältnamn i `delivery_nshift/models/nshift_request.py` mot din avtalstyp om du upptäcker avvikelser.
- API-täckning: rates, shipments (create + printset), pdfs, trackingstatus, cancel.

### Sendify
- **Inställningar → Lager → Sendify**: API-key (Bearer-token).
- API-täckning: quotes, bookings, label, get/cancel.

## Arkitektur

```
                     ┌──────────────────────────┐
                     │ delivery_shipping_base   │
                     │  • ShippingClient (bas)  │
                     │  • shipping.api.log      │
                     │  • produktfält + status  │
                     └──────────┬───────────────┘
                                │
        ┌───────────────────────┼─────────────────────────┐
        │                       │                         │
┌───────▼─────────┐    ┌────────▼────────┐    ┌──────────▼──────────┐
│ delivery_       │    │ delivery_nshift │    │ delivery_sendify    │
│ fraktjakt       │    │  REST/Basic     │    │  REST/Bearer        │
│  XML/consignor  │    │                 │    │                     │
└───────┬─────────┘    └─────────────────┘    └─────────────────────┘
        │
   ┌────┴───────┬──────────────┐
   │            │              │
┌──▼──────┐ ┌──▼──────┐ ┌─────▼─────┐
│ portal  │ │ returns │ │ (befintlig │
│         │ │         │ │  framtid)  │
└─────────┘ └─────────┘ └────────────┘
```

## Smoke-test

Alla klienter har offline-tester som körs med:

```bash
# Från frakttjänster integration/
python3 -c "from delivery_shipping_base.models.shipping_client import ShippingClient; print('OK')"
```

Testerna verifierar Basic-auth-konstruktion (nShift), Bearer-auth (Sendify),
Retry-After-hantering, hemlighets-maskering i logg, och Fraktjakts XML-byggande.

## Status

| Funktion | Fraktjakt | nShift | Sendify |
|----------|-----------|--------|---------|
| Prisförfrågan | ✅ | ✅ skeleton | ✅ skeleton |
| Bokning | ✅ | ✅ skeleton | ✅ skeleton |
| Fraktsedel-PDF | ✅ | ✅ skeleton | ✅ skeleton |
| Spårning | ✅ | ✅ skeleton | ⏳ |
| Webhook | ✅ | — | — |
| Avbokning | ✅ | ✅ skeleton | ✅ skeleton |
| Retur | ✅ | — | — |
| Ombudsval | ✅ | — | — |

✅ = implementerad och offline-testad
⏳ = inte i V1
skeleton = klient finns men kräver verifiering mot avtal/dokumentation

## Krav

- Odoo 19 (Enterprise eller Community)
- Python: `requests` (standard i Odoo-installationer)
- HTTPS-nåbar instans för Fraktjakts webhook

## Underhållstips

- Anropsloggen rensas dagligen efter 90 dagar via cron-jobbet `Shipping: städa logg äldre än 90 dagar`.
- Sätt `mode=test` för nShift och `sendify_test_mode=True` när du integrerar.
- nShift och Sendify är skeleton — kontrollera fältnamn (camelCase vs snake_case, currency vs amount-objekt) mot din specifika onboarding innan produktion.
