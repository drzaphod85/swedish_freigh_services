# -*- coding: utf-8 -*-
"""
Shared product fields needed by all shipping integrations.
"""
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # Customs
    shipping_taric = fields.Char(
        string="TARIC / HS Code",
        help="Customs code per the EU nomenclature. Required for "
             "international shipments.",
    )
    shipping_country_of_origin_id = fields.Many2one(
        "res.country", string="Country of Origin",
        help="ISO 3166-1 alpha-2 code sent to the carrier for customs "
             "declaration.",
    )

    # Dimensions
    product_length = fields.Float(
        string="Length (cm)", digits=(10, 2),
        help="Length in centimeters used by parcel calculation.")
    product_width = fields.Float(string="Width (cm)", digits=(10, 2))
    product_height = fields.Float(string="Height (cm)", digits=(10, 2))

    # Special handling
    shipping_dangerous_goods = fields.Boolean(string="Dangerous Goods (LQ)")
    shipping_dangerous_goods_un_nr = fields.Char(string="UN Number")
    shipping_in_own_parcel = fields.Boolean(
        string="Must Ship in Own Parcel",
        help="Prevents bin-packing algorithms from combining this product "
             "with other items.",
    )


class ProductProduct(models.Model):
    _inherit = "product.product"

    product_length = fields.Float(related="product_tmpl_id.product_length",
                                  store=True, readonly=False)
    product_width = fields.Float(related="product_tmpl_id.product_width",
                                 store=True, readonly=False)
    product_height = fields.Float(related="product_tmpl_id.product_height",
                                  store=True, readonly=False)

    def shipping_get_origin_country(self):
        """Return ISO 3166-1 alpha-2 code for country of origin.
        Use Odoo's standard `country_of_origin_id` if present (set by the
        account / stock_landed_costs modules), otherwise fall back to our
        own field."""
        self.ensure_one()
        if "country_of_origin_id" in self._fields:
            country = self.country_of_origin_id
            if country:
                return country.code
        return (self.shipping_country_of_origin_id.code
                if self.shipping_country_of_origin_id else "")
