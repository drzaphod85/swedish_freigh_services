# -*- coding: utf-8 -*-
"""Hooks delivery_type='sendify' into Odoo's delivery.carrier."""
import base64
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

from .sendify_request import SendifyClient
from odoo.addons.delivery_shipping_base.models.shipping_client import (
    ShippingApiError,
)

_logger = logging.getLogger(__name__)


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    delivery_type = fields.Selection(
        selection_add=[("sendify", "Sendify")],
        ondelete={"sendify": "set default"},
    )

    sendify_carrier_filter = fields.Char(
        string="Carrier Filter",
        help="e.g. 'postnord' or 'dhl' to limit responses in the quote API.")
    sendify_service_filter = fields.Char(
        string="Service Filter",
        help="e.g. 'mypack_collect'. Leave blank for cheapest option.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _sendify_get_client(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        if not company.sendify_api_key:
            raise UserError(_(
                "Sendify API key missing. Set it under Settings > Inventory "
                "> Sendify."))
        return SendifyClient(api_key=company.sendify_api_key, env=self.env)

    def _sendify_payload(self, partner_from, partner_to, parcels,
                         currency="SEK", reference=None):
        payload = {
            "from": SendifyClient.party_from_partner(partner_from),
            "to": SendifyClient.party_from_partner(partner_to),
            "parcels": parcels,
            "currency": currency,
            "reference": reference or "",
        }
        if self.sendify_carrier_filter:
            payload["carrier"] = self.sendify_carrier_filter
        if self.sendify_service_filter:
            payload["service"] = self.sendify_service_filter
        return payload

    # ------------------------------------------------------------------
    # Odoo API
    # ------------------------------------------------------------------
    def sendify_rate_shipment(self, order):
        self.ensure_one()
        client = self._sendify_get_client()
        company = order.company_id
        parcels = SendifyClient.parcels_from_lines(order.order_line)
        if not parcels:
            return {"success": False, "price": 0.0,
                    "error_message": _("No shippable products on this order."),
                    "warning_message": False}
        payload = self._sendify_payload(
            company.partner_id, order.partner_shipping_id,
            parcels, currency=order.currency_id.name or "SEK",
            reference=order.name)
        try:
            data = client.quote(payload)
        except ShippingApiError as e:
            return {"success": False, "price": 0.0,
                    "error_message": str(e), "warning_message": False}
        # Sendify typically responds with {"quotes": [...]}
        quotes = (data.get("quotes") if isinstance(data, dict) else data) or []
        if not quotes:
            return {"success": False, "price": 0.0,
                    "error_message": _("Sendify found no shipping options."),
                    "warning_message": False}
        chosen = min(quotes, key=lambda q: float(
            q.get("price") or q.get("total_price") or
            (q.get("amount") or {}).get("value") or 9e9))
        price = float(chosen.get("price") or chosen.get("total_price") or
                      (chosen.get("amount") or {}).get("value") or 0)
        return {"success": True, "price": price,
                "error_message": False, "warning_message": False}

    def sendify_send_shipping(self, pickings):
        self.ensure_one()
        client = self._sendify_get_client()
        results = []
        for picking in pickings:
            results.append(self._sendify_book(client, picking))
        return results

    def _sendify_book(self, client, picking):
        company = picking.company_id
        partner_from = (picking.picking_type_id.warehouse_id.partner_id or
                        company.partner_id)
        parcels = SendifyClient.parcels_from_lines(picking.move_ids)
        if not parcels:
            raise UserError(_("No parcels to ship for %s.") % picking.name)
        payload = self._sendify_payload(
            partner_from, picking.partner_id, parcels,
            currency=company.currency_id.name or "SEK",
            reference=picking.name)
        booking = client.book(payload, picking=picking)
        booking_id = booking.get("id") or booking.get("booking_id")
        tracking_number = (booking.get("tracking_number") or
                           booking.get("tracking_no") or "")

        # Fetch the label
        try:
            pdf_bytes = client.get_label(booking_id, picking=picking)
            self.env["ir.attachment"].create({
                "name": "Sendify - %s.pdf" % picking.name,
                "type": "binary",
                "datas": base64.b64encode(pdf_bytes),
                "res_model": "stock.picking",
                "res_id": picking.id,
                "mimetype": "application/pdf",
            })
        except ShippingApiError as e:
            picking.message_post(
                body=_("Could not fetch Sendify label: %s") % e)

        picking.write({
            "carrier_tracking_ref": tracking_number,
            "sendify_booking_id": booking_id,
            "sendify_tracking_number": tracking_number,
            "sendify_tracking_url": booking.get("tracking_url") or "",
            "sendify_label_url": booking.get("label_url") or "",
            "shipping_state": "ordered",
            "shipping_integration": "sendify",
        })
        picking.message_post(body=_(
            "Sendify booking created: %s, tracking %s") % (
            booking_id, tracking_number or "—"))
        return {"exact_price": float(booking.get("price") or 0.0),
                "tracking_number": tracking_number}

    def sendify_get_tracking_link(self, picking):
        if picking.sendify_tracking_url:
            return picking.sendify_tracking_url
        if picking.sendify_tracking_number:
            return ("https://track.sendify.se/?tracking=%s" %
                    picking.sendify_tracking_number)
        return False

    def sendify_cancel_shipment(self, picking):
        if not picking.sendify_booking_id:
            return True
        client = self._sendify_get_client()
        ok = client.cancel_booking(picking.sendify_booking_id, picking=picking)
        if ok:
            picking.write({"shipping_state": "cancelled",
                           "carrier_tracking_ref": False})
            picking.message_post(body=_("Sendify booking cancelled."))
        return ok

    def action_sendify_test_credentials(self):
        self.ensure_one()
        client = self._sendify_get_client()
        # Sendify rarely has a dedicated ping endpoint.
        # Test by sending a quote with dummy data.
        try:
            data = client.quote({
                "from": {"postal_code": "11122", "country": "SE"},
                "to": {"postal_code": "41115", "country": "SE"},
                "parcels": [{"weight": 1, "length": 20, "width": 20, "height": 10}],
                "currency": "SEK",
            })
        except ShippingApiError as e:
            raise UserError(str(e))
        n = len(data.get("quotes") or []) if isinstance(data, dict) \
            else len(data or [])
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Sendify OK"),
                "message": _("Connected — %d quotes returned") % n,
                "type": "success",
            },
        }
