# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    nshift_developer_id = fields.Char(string="nShift Developer ID")
    nshift_developer_key = fields.Char(string="nShift Developer Key",
                                       help="Treat as a password.")
    nshift_customer_no = fields.Char(string="nShift Customer Number",
                                     help="Found in nShift Online under "
                                          "company settings.")
    nshift_mode = fields.Selection(
        [("test", "Test"), ("prod", "Production")],
        default="test", string="nShift Mode")
    nshift_default_service = fields.Char(
        string="Default Service",
        help="e.g. PNL01 (PostNord MyPack Collect). Leave blank to let "
             "nShift autoselect.")
