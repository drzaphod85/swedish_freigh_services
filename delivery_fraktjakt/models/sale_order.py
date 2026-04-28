# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # Stash the latest Query API response so Order API type 1 can reuse
    # the shipment_id instead of running a fresh price query.
    fraktjakt_query_shipment_id = fields.Char(
        string="Fraktjakt query shipment", copy=False, readonly=True)
    fraktjakt_query_product_id = fields.Char(
        string="Selected shipping_product_id", copy=False)
    fraktjakt_agent_id = fields.Char(
        string="Selected service point", copy=False,
        help="Fraktjakt agent_id selected by the customer at checkout.")

    def _action_confirm(self):
        # Propagate selected service point to all pickings created on confirm.
        res = super()._action_confirm()
        for order in self:
            if order.fraktjakt_agent_id:
                pickings = order.picking_ids.filtered(
                    lambda p: p.carrier_id.delivery_type == "fraktjakt")
                pickings.write({"fraktjakt_agent_id": order.fraktjakt_agent_id})
        return res
