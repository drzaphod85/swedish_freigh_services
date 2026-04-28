# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    fraktjakt_consignor_id = fields.Char(
        related="company_id.fraktjakt_consignor_id", readonly=False)
    fraktjakt_consignor_key = fields.Char(
        related="company_id.fraktjakt_consignor_key", readonly=False)
    fraktjakt_test_mode = fields.Boolean(
        related="company_id.fraktjakt_test_mode", readonly=False)
    fraktjakt_callback_token = fields.Char(
        related="company_id.fraktjakt_callback_token", readonly=False)
    fraktjakt_default_export_reason = fields.Selection(
        related="company_id.fraktjakt_default_export_reason", readonly=False)
    fraktjakt_eori = fields.Char(related="company_id.fraktjakt_eori",
                                 readonly=False)
    fraktjakt_ioss = fields.Char(related="company_id.fraktjakt_ioss",
                                 readonly=False)
    fraktjakt_voec = fields.Char(related="company_id.fraktjakt_voec",
                                 readonly=False)
    fraktjakt_gb_vat = fields.Char(related="company_id.fraktjakt_gb_vat",
                                   readonly=False)
    fraktjakt_mva_num = fields.Char(related="company_id.fraktjakt_mva_num",
                                    readonly=False)
