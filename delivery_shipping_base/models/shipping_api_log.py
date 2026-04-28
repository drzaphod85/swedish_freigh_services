# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models


class ShippingApiLog(models.Model):
    _name = "shipping.api.log"
    _description = "Shipping integration API log"
    _order = "create_date desc"
    _rec_name = "endpoint"

    integration = fields.Char(string="Integration", required=True, index=True,
                              help="e.g. 'fraktjakt', 'nshift', 'sendify'.")
    endpoint = fields.Char(string="Endpoint", required=True, index=True)
    http_status = fields.Integer(string="HTTP")
    request_body = fields.Text(string="Request")
    response_body = fields.Text(string="Response")
    error = fields.Text(string="Error")
    picking_id = fields.Many2one("stock.picking", string="Transfer",
                                 ondelete="set null", index=True)
    create_date = fields.Datetime(readonly=True)
    create_uid = fields.Many2one("res.users", readonly=True)

    @api.model
    def _shipping_cleanup_old(self, days=90):
        """Cron function: delete log rows older than `days` days."""
        cutoff = fields.Datetime.now() - timedelta(days=days)
        old = self.search([("create_date", "<", cutoff)])
        count = len(old)
        old.unlink()
        return count
