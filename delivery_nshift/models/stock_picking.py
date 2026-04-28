# -*- coding: utf-8 -*-
from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    nshift_shipment_id = fields.Char(string="nShift shipment ID",
                                     copy=False, readonly=True, index=True)
    nshift_tracking_number = fields.Char(string="nShift tracking number",
                                         copy=False, readonly=True)
