# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    fraktjakt_consignor_id = fields.Char(
        string="Fraktjakt Consignor ID",
        help="Retrieved from Fraktjakt's integration settings.",
    )
    fraktjakt_consignor_key = fields.Char(
        string="Fraktjakt Consignor Key",
        help="Secret key — treat as a password. Retrieved from Fraktjakt's "
             "integration settings.",
    )
    fraktjakt_test_mode = fields.Boolean(
        string="Fraktjakt Test Mode",
        help="When enabled, all calls are logged extra verbosely and a "
             "banner is shown on shipping bookings. The actual test mode "
             "is enabled in Fraktjakt's UI on the integration level.",
        default=True,
    )
    fraktjakt_callback_token = fields.Char(
        string="Webhook Token",
        help="Random string used as the secret in the webhook URL "
             "/fraktjakt/webhook/<token>. Paste the same value in "
             "Fraktjakt's callback URL.",
        groups="base.group_system",
    )
    fraktjakt_default_export_reason = fields.Selection(
        [("SALE", "Sale"),
         ("GIFT", "Gift"),
         ("SAMPLE", "Sample"),
         ("RETURN", "Return"),
         ("REPAIR", "Repair"),
         ("PERSONAL EFFECTS", "Personal effects")],
        string="Default Export Reason",
        default="SALE",
    )
    fraktjakt_eori = fields.Char(string="EORI Number")
    fraktjakt_ioss = fields.Char(string="IOSS Number")
    fraktjakt_voec = fields.Char(string="VOEC Number (Norway)")
    fraktjakt_gb_vat = fields.Char(string="UK VAT Number")
    fraktjakt_mva_num = fields.Char(string="Norwegian MVA Number")
