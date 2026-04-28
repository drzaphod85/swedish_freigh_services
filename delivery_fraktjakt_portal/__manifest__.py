# -*- coding: utf-8 -*-
{
    "name": "Fraktjakt – customer portal & service point picker",
    "version": "19.0.1.0.0",
    "summary": "Show Fraktjakt tracking in the portal and let customers "
               "pick a service point at checkout.",
    "description": """
Adds three things:
1. Tracking block on portal order details (portal/my/orders/<id>)
2. Status history per shipment in the portal
3. Service point picker (Service Point Locator) in the website_sale checkout
    """,
    "author": "Familjen Larsson",
    "license": "LGPL-3",
    "category": "Inventory/Delivery",
    "depends": [
        "delivery_fraktjakt",
        "portal",
        "website_sale",
    ],
    "data": [
        "views/portal_templates.xml",
        "views/website_sale_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "delivery_fraktjakt_portal/static/src/scss/portal.scss",
            "delivery_fraktjakt_portal/static/src/js/agent_picker.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
