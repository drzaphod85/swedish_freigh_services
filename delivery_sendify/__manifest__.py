# -*- coding: utf-8 -*-
{
    "name": "Sendify – shipping integration",
    "version": "19.0.1.0.0",
    "summary": "Book shipments and fetch labels via Sendify (api.sendify.se).",
    "description": """
Sendify integration for Odoo 19
================================

Integration against the Sendify REST API. Handles:
* Quotes
* Bookings (create shipment + get label)
* Bearer-token auth with API key

NOTE: Skeleton implementation. Verify field names and URLs against your
Sendify onboarding before going to production.
    """,
    "author": "Familjen Larsson",
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
        "views/res_config_settings_views.xml",
        "views/delivery_carrier_views.xml",
        "views/stock_picking_views.xml",
        "views/sendify_menu.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
