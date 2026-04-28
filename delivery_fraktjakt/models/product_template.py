# -*- coding: utf-8 -*-
"""
Fraktjakt-specific product fields. Generic shipping fields (TARIC,
dimensions, country of origin, dangerous goods) live in
delivery_shipping_base.

The aliases below exist so older code that referenced fraktjakt_taric
or fraktjakt_country_of_manufacture keeps working.
"""
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # Backwards-compatible aliases against the base module's fields.
    # Used internally by delivery_fraktjakt code so we can rename later
    # without breaking upgrades.
    fraktjakt_taric = fields.Char(
        related="shipping_taric", readonly=False)
    fraktjakt_country_of_manufacture = fields.Many2one(
        related="shipping_country_of_origin_id", readonly=False)
    fraktjakt_dangerous_goods = fields.Boolean(
        related="shipping_dangerous_goods", readonly=False)
    fraktjakt_dangerous_goods_un_nr = fields.Char(
        related="shipping_dangerous_goods_un_nr", readonly=False)
    fraktjakt_in_own_parcel = fields.Boolean(
        related="shipping_in_own_parcel", readonly=False)


class ProductProduct(models.Model):
    _inherit = "product.product"

    def fraktjakt_get_origin_country(self):
        """Backwards-compatible alias for shipping_get_origin_country."""
        return self.shipping_get_origin_country()
