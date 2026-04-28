# -*- coding: utf-8 -*-
"""
Sendify REST client.

Built on top of ShippingClient (delivery_shipping_base). Sendify's API
uses a Bearer API key and JSON.

Skeleton: Verify field names against your Sendify onboarding documentation
before production.
"""
import logging

from odoo import _

from odoo.addons.delivery_shipping_base.models.shipping_client import (
    ShippingApiError,
    ShippingClient,
)

_logger = logging.getLogger(__name__)

# Sendify uses x-api-key header authentication (not Bearer).
# API key is retrieved from https://web.sendify.se/settings/api
# Production base URL — Sendify does not publish a sandbox host.
PROD_BASE = "https://api.sendify.com/v1"


class SendifyClient(ShippingClient):
    integration_name = "sendify"

    def __init__(self, api_key, env=None,
                 log_model="shipping.api.log"):
        super().__init__(env=env, log_model=log_model)
        self.api_key = api_key
        self.base_url = PROD_BASE

    def _auth_headers(self):
        return {
            "x-api-key": self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Public operations
    # ------------------------------------------------------------------
    def quote(self, payload, picking=None):
        """POST /quotes — rate quote.

        Payload format (best guess based on common Sendify usage)::

            {
                "from": {...},
                "to": {...},
                "parcels": [{"weight":1.5,"length":30,"width":20,"height":10}],
                "currency": "SEK"
            }
        """
        resp = self.post(f"{self.base_url}/quotes",
                         headers=self._auth_headers(),
                         json_body=payload, picking=picking)
        return self.parse_json_or_raise(resp)

    def book(self, payload, picking=None):
        """POST /bookings — book shipping.

        Expected response: {id, status, tracking_number, label_url, ...}
        """
        resp = self.post(f"{self.base_url}/bookings",
                         headers=self._auth_headers(),
                         json_body=payload, picking=picking)
        return self.parse_json_or_raise(resp)

    def get_label(self, booking_id, picking=None):
        """GET /bookings/{id}/label — fetch the label as PDF bytes."""
        resp = self.get(
            f"{self.base_url}/bookings/{booking_id}/label",
            headers={**self._auth_headers(), "Accept": "application/pdf"},
            picking=picking)
        if not resp.ok:
            raise ShippingApiError(_(
                "Could not fetch Sendify label: %s") % resp.text)
        return resp.content

    def get_booking(self, booking_id, picking=None):
        resp = self.get(f"{self.base_url}/bookings/{booking_id}",
                        headers=self._auth_headers(), picking=picking)
        return self.parse_json_or_raise(resp)

    def cancel_booking(self, booking_id, picking=None):
        resp = self.delete(f"{self.base_url}/bookings/{booking_id}",
                           headers=self._auth_headers(), picking=picking)
        return resp.status_code in (200, 202, 204)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def party_from_partner(partner):
        if not partner:
            return {}
        return {
            "name": partner.commercial_company_name
                    or partner.name or "",
            "contact_name": partner.name or "",
            "address_line_1": partner.street or "",
            "address_line_2": partner.street2 or "",
            "postal_code": (partner.zip or "").replace(" ", ""),
            "city": partner.city or "",
            "country": (partner.country_id and
                        partner.country_id.code) or "SE",
            "phone": partner.phone or partner.mobile or "",
            "email": partner.email or "",
            "vat_number": partner.vat or "",
            "is_residential": not partner.is_company,
        }

    @staticmethod
    def parcels_from_lines(lines):
        parcels = []
        for line in lines:
            product = line.product_id
            if not product or product.type == "service":
                continue
            qty = (line.product_uom_qty if hasattr(line, "product_uom_qty")
                   else line.quantity)
            if qty <= 0:
                continue
            for _ in range(int(qty)):
                parcels.append({
                    "weight": round(product.weight or 0.1, 3),
                    "length": product.product_length or 1,
                    "width": product.product_width or 1,
                    "height": product.product_height or 1,
                    "description": product.name or "",
                })
        return parcels
