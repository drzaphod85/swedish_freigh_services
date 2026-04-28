# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    nshift_developer_id = fields.Char(
        related="company_id.nshift_developer_id", readonly=False)
    nshift_developer_key = fields.Char(
        related="company_id.nshift_developer_key", readonly=False)
    nshift_customer_no = fields.Char(
        related="company_id.nshift_customer_no", readonly=False)
    nshift_mode = fields.Selection(
        related="company_id.nshift_mode", readonly=False)
    nshift_default_service = fields.Char(
        related="company_id.nshift_default_service", readonly=False)
