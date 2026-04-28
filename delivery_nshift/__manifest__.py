# -*- coding: utf-8 -*-
{
    "name": "nShift Ship – shipping integration",
    "version": "19.0.1.0.0",
    "summary": "Book shipments and create labels via nShift Ship "
               "(formerly Unifaun Online Connect).",
    "description": """
nShift Ship integration for Odoo 19
====================================

Integration against the nShift Ship REST API
(api.unifaun.com/rs-extapi/v1). Handles:
* Rate quotes
* Shipment creation
* PDF labels
* HTTP Basic auth with Developer ID + Customer credentials

NOTE: This is a skeleton implementation based on public documentation.
Adjust fields in nshift_request.py once you have your actual credentials
and know the exact response format in your environment.
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
        "views/nshift_menu.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
