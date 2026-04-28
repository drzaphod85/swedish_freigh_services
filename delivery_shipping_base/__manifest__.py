# -*- coding: utf-8 -*-
{
    "name": "Shipping Base – shared models for shipping integrations",
    "version": "19.0.1.0.0",
    "summary": "Shared models and fields used by delivery_fraktjakt, "
               "delivery_nshift and delivery_sendify.",
    "description": """
Base module that does nothing on its own — it only defines shared
models for:

* Product fields: TARIC, country of origin, dimensions (cm), dangerous goods
* shipping.api.log: shared log row for all outgoing API calls
* Status sequence on stock.picking (shipped, at agent, delivered, etc.)
* Abstract Python base class `ShippingClient` with rate-limit and retry
    """,
    "author": "Familjen Larsson",
    "license": "LGPL-3",
    "category": "Inventory/Delivery",
    "depends": [
        "delivery",
        "stock",
    ],
    "external_dependencies": {
        "python": ["requests"],
    },
    "data": [
        "security/ir.model.access.csv",
        "views/shipping_log_views.xml",
        "views/product_template_views.xml",
        "views/stock_picking_views.xml",
        "views/shipping_menu.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
