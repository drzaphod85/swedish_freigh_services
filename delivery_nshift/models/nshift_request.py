# -*- coding: utf-8 -*-
"""
nShift Ship REST client.

Built on top of ShippingClient (delivery_shipping_base) and covers:
- /addresses (for validation)
- /shipments (create shipment)
- /rates (rate quote, if enabled on the contract)
- /pdfs (fetch labels as PDF)

Auth: HTTP Basic — username = developer-id + customer-no combined per
nShift's integration guide. For simpler setups, use a "developer key" as
user and a token as password.

Skeleton: Verify field names against your contract type before
production use.
"""
import base64
import logging

from odoo import _

from odoo.addons.delivery_shipping_base.models.shipping_client import (
    ShippingApiError,
    ShippingClient,
)

_logger = logging.getLogger(__name__)

# nShift has two API hosts. Use test during development.
PROD_BASE = "https://api.unifaun.com/rs-extapi/v1"
TEST_BASE = "https://api.unifaun.com/rs-extapi/v1"  # same host, test keys
# Some nShift deployments have migrated to api.nshift.com.
# If you have issues with PROD_BASE — try "https://api.nshift.com/rs-extapi/v1".


class NshiftClient(ShippingClient):
    integration_name = "nshift"

    def __init__(self, developer_id, developer_key,
                 customer_no=None, mode="prod", env=None,
                 log_model="shipping.api.log"):
        super().__init__(env=env, log_model=log_model)
        self.developer_id = developer_id
        self.developer_key = developer_key
        self.customer_no = customer_no
        self.base_url = TEST_BASE if mode == "test" else PROD_BASE

    # ------------------------------------------------------------------
    # Auth headers
    # ------------------------------------------------------------------
    def _auth_headers(self):
        userpass = f"{self.developer_id}:{self.developer_key}"
        token = base64.b64encode(userpass.encode("utf-8")).decode("ascii")
        return {
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Public operations
    # ------------------------------------------------------------------
    def list_carriers(self):
        """GET /carriers — show which carriers you have contracts with."""
        resp = self.get(f"{self.base_url}/carriers",
                        headers=self._auth_headers())
        return self.parse_json_or_raise(resp)

    def rates(self, payload, picking=None):
        """POST /rates — rate quote for a draft shipment.

        payload: shipment dict in the nShift schema, e.g.::

            {
                "sender": {"name": "...", "address1": "...", ...},
                "receiver": {"name": "...", "address1": "...", ...},
                "service": {"id": "PNL01"},        # optional
                "parcels": [{"weight": 1.5, "valuePerParcel": True}],
                "test": true
            }
        """
        resp = self.post(f"{self.base_url}/rates",
                         headers=self._auth_headers(),
                         json_body=payload, picking=picking)
        return self.parse_json_or_raise(resp)

    def create_shipment(self, payload, picking=None, autoselect=True):
        """POST /shipments — create shipment.

        With autoselect=True we ask nShift to pick the cheapest/fastest
        service (if that logic is enabled on the contract).

        Returns a shipment dict with id, status, parcels.
        """
        if autoselect:
            payload = dict(payload, options={
                **(payload.get("options") or {}),
                "autoSelectService": True,
            })
        resp = self.post(f"{self.base_url}/shipments",
                         headers=self._auth_headers(),
                         json_body=payload, picking=picking)
        return self.parse_json_or_raise(resp)

    def confirm_shipment(self, shipment_id, picking=None):
        """POST /shipments/{id}/printset — flag as ready and fetch labels.

        nShift's "printset" is an abstraction: produces PDFs and may
        trigger EDI calls to the carrier.
        """
        resp = self.post(
            f"{self.base_url}/shipments/{shipment_id}/printset",
            headers=self._auth_headers(),
            json_body={"format": "PDF", "size": "A6"},
            picking=picking)
        return self.parse_json_or_raise(resp)

    def get_pdf(self, shipment_id, picking=None):
        """GET /shipments/{id}/pdfs — fetch the label as PDF bytes.

        Returns raw PDF bytes.
        """
        resp = self.get(
            f"{self.base_url}/shipments/{shipment_id}/pdfs",
            headers={
                **self._auth_headers(),
                "Accept": "application/pdf",
            },
            picking=picking)
        if not resp.ok:
            raise ShippingApiError(_(
                "Could not fetch label from nShift: %s") % resp.text)
        return resp.content

    def cancel_shipment(self, shipment_id, picking=None):
        """DELETE /shipments/{id} — cancel shipment before printing."""
        resp = self.delete(
            f"{self.base_url}/shipments/{shipment_id}",
            headers=self._auth_headers(), picking=picking)
        return resp.status_code in (200, 202, 204)

    def track(self, tracking_number, picking=None):
        """GET /trackingstatus — tracking. Available on some contracts.

        Skeleton — adjust the exact URL to your nShift version.
        """
        resp = self.get(
            f"{self.base_url}/trackingstatus/{tracking_number}",
            headers=self._auth_headers(), picking=picking)
        if resp.status_code == 404:
            return None
        return self.parse_json_or_raise(resp)

    # ------------------------------------------------------------------
    # Helpers for building payloads
    # ------------------------------------------------------------------
    @staticmethod
    def party_from_partner(partner, role="sender"):
        """Build a sender/receiver block from a res.partner."""
        if not partner:
            return {}
        return {
            "name": partner.commercial_company_name
                    or partner.name or "",
            "contact": partner.name or "",
            "address1": partner.street or "",
            "address2": partner.street2 or "",
            "zipcode": (partner.zip or "").replace(" ", ""),
            "city": partner.city or "",
            "state": partner.state_id and partner.state_id.code or "",
            "country": partner.country_id and partner.country_id.code or "SE",
            "phone": partner.phone or partner.mobile or "",
            "email": partner.email or "",
            "vatNo": partner.vat or "",
        }

    @staticmethod
    def parcels_from_lines(lines):
        """Build a parcels list. One parcel per non-service line — tweak
        for bin-packing if desired."""
        parcels = []
        for line in lines:
            product = line.product_id
            if not product or product.type == "service":
                continue
            qty = (line.product_uom_qty if hasattr(line, "product_uom_qty")
                   else line.quantity)
            if qty <= 0:
                continue
            parcels.append({
                "valuePerParcel": True,
                "copies": int(qty),
                "weight": round((product.weight or 0.1) * qty, 3),
                "length": product.product_length or 0,
                "width": product.product_width or 0,
                "height": product.product_height or 0,
                "contents": product.name or "",
            })
        return parcels
