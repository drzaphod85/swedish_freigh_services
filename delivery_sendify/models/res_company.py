# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    sendify_api_key = fields.Char(
        string="Sendify API Key",
        help="Bearer token. Retrieved from the Sendify portal under "
             "API settings.")
    sendify_test_mode = fields.Boolean(
        string="Sendify Test Mode", default=True,
        help="When enabled, calls are logged extra and no real bookings "
             "are created. Test mode must also be enabled at Sendify.")
