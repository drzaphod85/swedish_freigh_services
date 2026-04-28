# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    sendify_api_key = fields.Char(
        related="company_id.sendify_api_key", readonly=False)
    sendify_test_mode = fields.Boolean(
        related="company_id.sendify_test_mode", readonly=False)
