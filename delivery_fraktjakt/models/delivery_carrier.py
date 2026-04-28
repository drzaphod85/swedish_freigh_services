# -*- coding: utf-8 -*-
"""
Delivery carrier integration for Fraktjakt
==========================================

Hooks delivery_type='fraktjakt' into Odoo's standard delivery.carrier model.
Implements the four methods Odoo expects:
- fraktjakt_rate_shipment(order)        -> dict(success, price, error_message)
- fraktjakt_send_shipping(pickings)     -> list[dict(exact_price, tracking_number)]
- fraktjakt_get_tracking_link(picking)  -> str (URL)
- fraktjakt_cancel_shipment(picking)    -> bool
"""
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

from .fraktjakt_request import FraktjaktClient, FraktjaktError

_logger = logging.getLogger(__name__)


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    delivery_type = fields.Selection(
        selection_add=[("fraktjakt", "Fraktjakt")],
        ondelete={"fraktjakt": "set default"},
    )

    fraktjakt_shipping_product_id = fields.Char(
        string="Specific shipping_product_id",
        help="Leave blank to let Fraktjakt show all available services. "
             "Set to e.g. 30 (PostNord MyPack Collect) to always use a "
             "specific service.",
    )
    fraktjakt_no_agents = fields.Boolean(
        string="Skip Service Point Suggestions",
        help="Faster response — but no info about closest service point "
             "shown to the customer.",
    )
    fraktjakt_express = fields.Boolean(string="Express Only")
    fraktjakt_green = fields.Boolean(string="Green-certified Only")
    fraktjakt_quality = fields.Boolean(string="Quality-certified Only")
    fraktjakt_time_guarantee = fields.Boolean(string="Time Guarantee Only")
    fraktjakt_pickup = fields.Boolean(string="Pickup at Sender Only")
    fraktjakt_dropoff = fields.Boolean(string="Drop-off Only")
    fraktjakt_cold = fields.Boolean(string="Refrigerated Transport")
    fraktjakt_frozen = fields.Boolean(string="Frozen Transport")
    fraktjakt_insure_default = fields.Boolean(
        string="Additional Insurance",
        help="Automatically insure if value exceeds the carrier's basic "
             "insurance.",
    )
    fraktjakt_price_sort = fields.Selection(
        [("0", "Fastest delivery"),
         ("1", "Lowest price")],
        string="Sort Order",
        default="1",
    )
    fraktjakt_use_callback = fields.Boolean(
        string="Enable Webhook",
        default=True,
        help="Send callback_url with every call so Fraktjakt notifies us "
             "on status changes.",
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _fraktjakt_get_client(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        if not (company.fraktjakt_consignor_id and
                company.fraktjakt_consignor_key):
            raise UserError(_(
                "Fraktjakt credentials missing. Set Consignor ID and Key "
                "under Settings > Inventory > Fraktjakt."))
        currency = (self.env.company.currency_id.name or "SEK")
        return FraktjaktClient(
            consignor_id=company.fraktjakt_consignor_id,
            consignor_key=company.fraktjakt_consignor_key,
            currency=currency,
            language=self.env.lang and self.env.lang[:2] or "sv",
            env=self.env,
            log_model="shipping.api.log",
        )

    def _fraktjakt_callback_url(self):
        company = self.company_id or self.env.company
        if not self.fraktjakt_use_callback or not company.fraktjakt_callback_token:
            return False
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        if not base:
            return False
        return "%s/fraktjakt/webhook/%s" % (
            base.rstrip("/"), company.fraktjakt_callback_token)

    @staticmethod
    def _fraktjakt_address_from_partner(partner):
        if not partner:
            return {}
        return {
            "street_address_1": (partner.street or "")[:35],
            "street_address_2": (partner.street2 or "")[:35],
            "postal_code": (partner.zip or "").replace(" ", ""),
            "city_name": partner.city or "",
            "country_code": (partner.country_id.code or "SE"),
            "residential": "1" if not partner.is_company else "0",
            "language": (partner.lang or "sv")[:2],
        }

    def _fraktjakt_party(self, partner):
        if not partner:
            return {}
        return {
            "company": partner.commercial_company_name or partner.name or "",
            "name_to": partner.name or "",
            "telephone_to": partner.phone or partner.mobile or "",
            "email_to": partner.email or "",
            "tax_id": partner.vat or "",
            "address": self._fraktjakt_address_from_partner(partner),
        }

    @staticmethod
    def _fraktjakt_commodities_from_lines(lines, currency_name="SEK"):
        commodities = []
        for line in lines:
            product = line.product_id
            if not product or product.type == "service":
                continue
            qty = line.product_uom_qty if hasattr(line, "product_uom_qty") \
                else line.quantity
            if qty <= 0:
                continue
            commodities.append({
                "name": (product.name or "")[:80],
                "description": (product.description_sale
                                or product.name or "")[:200],
                "quantity": int(qty),
                "quantity_units": "EA",
                "weight": round((product.weight or 0.1) * qty, 3),
                "length": product.product_length or 0,
                "width": product.product_width or 0,
                "height": product.product_height or 0,
                "unit_price": round(line.price_unit if hasattr(line, "price_unit")
                                    else (product.list_price or 0), 2),
                "currency": currency_name,
                "article_number": product.default_code or "",
                "taric": product.shipping_taric or "",
                "country_of_manufacture":
                    product.shipping_get_origin_country(),
            })
        return commodities

    # ------------------------------------------------------------------
    # Odoo API: Rate
    # ------------------------------------------------------------------
    def fraktjakt_rate_shipment(self, order):
        """Called at checkout / on SO to compute shipping cost."""
        self.ensure_one()
        client = self._fraktjakt_get_client()
        currency = order.currency_id.name or "SEK"
        commodities = self._fraktjakt_commodities_from_lines(
            order.order_line, currency_name=currency)
        if not commodities:
            return {
                "success": False,
                "price": 0.0,
                "error_message": _("No shippable products on this order."),
                "warning_message": False,
            }
        try:
            result = client.query(
                address_to=self._fraktjakt_address_from_partner(
                    order.partner_shipping_id),
                commodities=commodities,
                shipping_product_id=self.fraktjakt_shipping_product_id or None,
                callback_url=self._fraktjakt_callback_url(),
                reference=order.name,
                no_agents=self.fraktjakt_no_agents,
                cold=self.fraktjakt_cold,
                frozen=self.fraktjakt_frozen,
                express=self.fraktjakt_express,
                value=order.amount_untaxed,
            )
        except FraktjaktError as e:
            return {
                "success": False,
                "price": 0.0,
                "error_message": str(e),
                "warning_message": False,
            }
        if not result["products"]:
            return {
                "success": False,
                "price": 0.0,
                "error_message": _(
                    "Fraktjakt returned no shipping options for this address."),
                "warning_message": False,
            }
        # Pick cheapest or specific service
        if self.fraktjakt_shipping_product_id:
            chosen = next((p for p in result["products"]
                           if p["id"] == self.fraktjakt_shipping_product_id),
                          result["products"][0])
        else:
            chosen = min(result["products"], key=lambda p: p["price"])
        # Save shipment_id for Order API type 1
        order.fraktjakt_query_shipment_id = result["shipment_id"]
        order.fraktjakt_query_product_id = chosen["id"]
        return {
            "success": True,
            "price": chosen["price"],
            "error_message": False,
            "warning_message": False,
        }

    # ------------------------------------------------------------------
    # Odoo API: Send
    # ------------------------------------------------------------------
    def fraktjakt_send_shipping(self, pickings):
        """Create shipping orders for one or more pickings."""
        self.ensure_one()
        client = self._fraktjakt_get_client()
        results = []
        for picking in pickings:
            results.append(self._fraktjakt_book_picking(client, picking))
        return results

    def _fraktjakt_book_picking(self, client, picking):
        company = picking.company_id
        sale = picking.sale_id
        # Run a fresh query if none stored or older than 5 days
        shipment_id = sale.fraktjakt_query_shipment_id if sale else False
        chosen_product_id = (sale.fraktjakt_query_product_id if sale else False) \
            or self.fraktjakt_shipping_product_id

        if not shipment_id:
            commodities = self._fraktjakt_commodities_from_lines(
                picking.move_ids,
                currency_name=company.currency_id.name or "SEK")
            query = client.query(
                address_to=self._fraktjakt_address_from_partner(
                    picking.partner_id),
                commodities=commodities,
                shipping_product_id=chosen_product_id,
                callback_url=self._fraktjakt_callback_url(),
                reference=picking.name,
                no_agents=self.fraktjakt_no_agents,
                cold=self.fraktjakt_cold,
                frozen=self.fraktjakt_frozen,
                picking=picking,
            )
            shipment_id = query["shipment_id"]
            if not chosen_product_id and query["products"]:
                chosen_product_id = min(
                    query["products"], key=lambda p: p["price"])["id"]

        # Create the actual shipping order
        sender_partner = picking.picking_type_id.warehouse_id.partner_id \
            or company.partner_id
        recipient_party = self._fraktjakt_party(picking.partner_id)
        sender_party = self._fraktjakt_party(sender_partner)
        # Add customs info from the company on sender
        sender_party.update({
            "eori": company.fraktjakt_eori or "",
            "ioss": company.fraktjakt_ioss or "",
            "voec": company.fraktjakt_voec or "",
            "gb_vat": company.fraktjakt_gb_vat or "",
            "mva_num": company.fraktjakt_mva_num or "",
        })
        order_resp = client.order(
            shipment_id=shipment_id,
            shipping_product_id=chosen_product_id,
            agent_id=picking.fraktjakt_agent_id or None,
            no_agents=self.fraktjakt_no_agents,
            sender=sender_party,
            recipient=recipient_party,
            callback_url=self._fraktjakt_callback_url(),
            reference=picking.name,
            export_reason=company.fraktjakt_default_export_reason,
            picking=picking,
        )

        # Write to picking
        picking.write({
            "carrier_tracking_ref": order_resp.get("tracking_number") or "",
            "fraktjakt_shipment_id": order_resp.get("shipment_id"),
            "fraktjakt_access_code": order_resp.get("access_code"),
            "fraktjakt_access_link": order_resp.get("access_link"),
            "fraktjakt_tracking_code": order_resp.get("tracking_code"),
            "fraktjakt_tracking_link": order_resp.get("tracking_link"),
            "fraktjakt_tracking_number": order_resp.get("tracking_number"),
            "fraktjakt_amount": order_resp.get("amount"),
            "fraktjakt_currency": order_resp.get("currency"),
            "fraktjakt_return_link": order_resp.get("return_link"),
            "fraktjakt_cancel_link": order_resp.get("cancel_link"),
            "fraktjakt_state": "ordered",
        })

        # Fetch the label (may not be available in test mode — then 0 docs)
        try:
            docs = client.shipping_documents(
                order_resp["shipment_id"], picking=picking)
            for d in docs:
                self.env["ir.attachment"].create({
                    "name": "Fraktjakt - %s" % d["name"],
                    "type": "binary",
                    "datas": d["file_b64"],
                    "res_model": "stock.picking",
                    "res_id": picking.id,
                    "mimetype": "application/pdf",
                })
        except FraktjaktError as e:
            picking.message_post(
                body=_("Shipping label not yet available: %s") % e)

        picking.message_post(body=_(
            "Fraktjakt booking created: <a href='%s' target='_blank'>"
            "shipment %s</a>. Tracking: %s") % (
            order_resp.get("access_link") or "",
            order_resp.get("shipment_id") or "",
            order_resp.get("tracking_number") or "—"))

        return {
            "exact_price": order_resp.get("amount") or 0.0,
            "tracking_number": order_resp.get("tracking_number") or "",
        }

    # ------------------------------------------------------------------
    # Odoo API: Tracking link
    # ------------------------------------------------------------------
    def fraktjakt_get_tracking_link(self, picking):
        if picking.fraktjakt_tracking_link:
            return picking.fraktjakt_tracking_link
        if picking.fraktjakt_tracking_code:
            locale = (self.env.lang or "sv")[:2]
            return "https://www.fraktjakt.se/trace/shipment/%s&locale=%s" % (
                picking.fraktjakt_tracking_code, locale)
        return False

    # ------------------------------------------------------------------
    # Odoo API: Cancel
    # ------------------------------------------------------------------
    def fraktjakt_cancel_shipment(self, picking):
        if picking.fraktjakt_cancel_link:
            try:
                import requests
                requests.get(picking.fraktjakt_cancel_link, timeout=15)
            except Exception as e:
                _logger.warning("Fraktjakt cancellation failed: %s", e)
                raise UserError(_(
                    "Cancellation at Fraktjakt failed. Cancel manually at "
                    "%s") % picking.fraktjakt_access_link)
        picking.write({
            "fraktjakt_state": "cancelled",
            "carrier_tracking_ref": False,
        })
        picking.message_post(body=_("Fraktjakt booking cancelled."))
        return True

    # ------------------------------------------------------------------
    # Button: test credentials and fetch available shipping_products
    # ------------------------------------------------------------------
    def action_fraktjakt_test_credentials(self):
        self.ensure_one()
        client = self._fraktjakt_get_client()
        try:
            status = client.status()
        except FraktjaktError as e:
            raise UserError(str(e))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Fraktjakt OK"),
                "message": _("Server status: %s") % status.get("server_status"),
                "type": "success",
                "sticky": False,
            },
        }
