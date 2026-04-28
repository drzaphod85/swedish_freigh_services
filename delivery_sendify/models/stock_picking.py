# -*- coding: utf-8 -*-
from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    sendify_booking_id = fields.Char(string="Sendify booking ID",
                                     copy=False, readonly=True, index=True)
    sendify_tracking_number = fields.Char(string="Sendify tracking number",
                                          copy=False, readonly=True)
    sendify_tracking_url = fields.Char(string="Sendify tracking link",
                                       copy=False, readonly=True)
    sendify_label_url = fields.Char(string="Sendify label URL",
                                    copy=False, readonly=True)
