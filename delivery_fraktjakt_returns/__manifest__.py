# -*- coding: utf-8 -*-
{
    "name": "Fraktjakt – customer-initiated returns",
    "version": "19.0.1.0.0",
    "summary": "Let customers request a return from the portal — return "
               "label is created automatically.",
    "description": """
Adds a "Request return" button to the customer portal for Fraktjakt
shipments. The button creates a return shipment at Fraktjakt via their
return_link and emails the return label to the customer.
    """,
    "author": "Familjen Larsson",
    "license": "LGPL-3",
    "category": "Inventory/Delivery",
    "depends": [
        "delivery_fraktjakt",
        "delivery_fraktjakt_portal",
        "stock",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/portal_return_templates.xml",
        "wizards/fraktjakt_return_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
