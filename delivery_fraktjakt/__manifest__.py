# -*- coding: utf-8 -*-
{
    "name": "Fraktjakt – shipping integration",
    "version": "19.0.1.0.0",
    "summary": "Book shipments and track parcels via Fraktjakt "
               "(PostNord, DHL, Schenker, Bring, etc.)",
    "description": """
Fraktjakt integration for Odoo 19
==================================

Complete integration against Fraktjakt's XML API (v4.10):

* Rate quotes at checkout via the Query API
* Booking on transfer validation via the Order API (type 1)
* Automatic retrieval of the shipping label (Shipping Documents API)
* Tracking link on transfer and sales order
* Webhook receiver for real-time updates
* Support for PostNord, DHL, Schenker, Bring, UPS, FedEx, DSV and more
* Customs support: TARIC, country of origin, description, EORI

Two complementary modules:
- delivery_fraktjakt_portal — agent picker at checkout + status details in
  the customer portal
- delivery_fraktjakt_returns — customer-initiated returns from the portal
    """,
    "author": "Familjen Larsson",
    "website": "https://www.fraktjakt.se",
    "license": "LGPL-3",
    "category": "Inventory/Delivery",
    "depends": [
        "delivery_shipping_base",
        "sale_management",
        "mail",
    ],
    "external_dependencies": {
        "python": ["requests"],
    },
    "data": [
        "security/ir.model.access.csv",
        "data/delivery_carrier_data.xml",
        "data/ir_cron_data.xml",
        "data/mail_template_data.xml",
        "views/res_config_settings_views.xml",
        "views/delivery_carrier_views.xml",
        "views/stock_picking_views.xml",
        "views/fraktjakt_menu.xml",
        "wizards/fraktjakt_register_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "delivery_fraktjakt/static/src/scss/fraktjakt.scss",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
