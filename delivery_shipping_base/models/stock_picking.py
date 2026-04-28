# -*- coding: utf-8 -*-
"""
Shared shipping status on stock.picking — complement to Odoo's own
state field. Set by the integrations as they receive status updates.
"""
from odoo import fields, models


SHIPPING_STATES = [
    ("draft", "Not Booked"),
    ("queried", "Quote Requested"),
    ("ordered", "Booked"),
    ("paid", "Paid"),
    ("in_transit", "In Transit"),
    ("at_agent", "At Service Point"),
    ("delivered", "Delivered"),
    ("returned", "Returned"),
    ("cancelled", "Cancelled"),
    ("error", "Error"),
]


class StockPicking(models.Model):
    _inherit = "stock.picking"

    shipping_state = fields.Selection(
        SHIPPING_STATES, string="Shipping Status",
        default="draft", copy=False, tracking=True,
        help="Overall status from the carrier regardless of which "
             "integration was used.",
    )
    shipping_last_event = fields.Char(string="Last Event", copy=False)
    shipping_last_event_at = fields.Datetime(string="Event Time", copy=False)
    shipping_integration = fields.Char(
        string="Shipping Integration", copy=False,
        help="Which integration booked the shipment — e.g. fraktjakt, "
             "nshift, sendify.")
