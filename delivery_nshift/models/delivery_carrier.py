# -*- coding: utf-8 -*-
"""
Hooks delivery_type='nshift' into Odoo's delivery.carrier.
"""
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

from .nshift_request import NshiftClient
from odoo.addons.delivery_shipping_base.models.shipping_client import (
    ShippingApiError,
)

_logger = logging.getLogger(__name__)


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    delivery_type = fields.Selection(
        selection_add=[("nshift", "nShift Ship")],
        ondelete={"nshift": "set default"},
    )

    nshift_service_id = fields.Char(
        string="Service ID",
        help="e.g. PNL01 for PostNord MyPack Collect. Leave blank to let "
             "nShift pick the cheapest/fastest.",
    )
    nshift_payer = fields.Selection(
        [("SENDER", "Sender"),
         ("RECEIVER", "Receiver"),
         ("THIRD_PARTY", "Third party")],
        default="SENDER", string="Payer")
    nshift_pdf_size = fields.Selection(
        [("A6", "A6 — thermal label"),
         ("A4", "A4 — plain paper")],
        default="A6")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _nshift_get_client(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        if not (company.nshift_developer_id and company.nshift_developer_key):
            raise UserError(_(
                "nShift credentials missing. Set Developer ID and Key under "
                "Settings > Inventory > nShift."))
        return NshiftClient(
            developer_id=company.nshift_developer_id,
            developer_key=company.nshift_developer_key,
            customer_no=company.nshift_customer_no,
            mode=company.nshift_mode or "test",
            env=self.env,
        )

    def _nshift_payload_from_picking(self, picking, sender_partner=None):
        """Assemble a shipment payload from a picking."""
        company = picking.company_id
        sender_partner = sender_partner or (
            picking.picking_type_id.warehouse_id.partner_id or
            company.partner_id)
        client_cls = NshiftClient
        return {
            "sender": client_cls.party_from_partner(sender_partner, "sender"),
            "receiver": client_cls.party_from_partner(picking.partner_id,
                                                     "receiver"),
            "service": ({"id": self.nshift_service_id}
                        if self.nshift_service_id else None),
            "parcels": client_cls.parcels_from_lines(picking.move_ids),
            "options": {
                "test": company.nshift_mode == "test",
                "payerCode": self.nshift_payer or "SENDER",
            },
            "senderReference": picking.name,
            "receiverReference": picking.sale_id.name if picking.sale_id else "",
        }

    # ------------------------------------------------------------------
    # Odoo API
    # ------------------------------------------------------------------
    def nshift_rate_shipment(self, order):
        """Call /rates to compute shipping cost on a SO."""
        self.ensure_one()
        client = self._nshift_get_client()
        company = order.company_id

        # Build a mini payload from SO lines
        payload = {
            "sender": NshiftClient.party_from_partner(
                company.partner_id, "sender"),
            "receiver": NshiftClient.party_from_partner(
                order.partner_shipping_id, "receiver"),
            "parcels": NshiftClient.parcels_from_lines(order.order_line),
            "service": ({"id": self.nshift_service_id}
                        if self.nshift_service_id else None),
            "options": {"test": company.nshift_mode == "test"},
        }
        if not payload["parcels"]:
            return {"success": False, "price": 0.0,
                    "error_message": _("No shippable products on this order."),
                    "warning_message": False}
        try:
            data = client.rates(payload)
        except ShippingApiError as e:
            return {"success": False, "price": 0.0,
                    "error_message": str(e), "warning_message": False}
        # nShift returns a list of rates with price objects
        rates = data if isinstance(data, list) else data.get("rates", [])
        if not rates:
            return {"success": False, "price": 0.0,
                    "error_message": _(
                        "nShift returned no shipping options."),
                    "warning_message": False}
        # Pick cheapest
        chosen = min(rates, key=lambda r: float(
            (r.get("price") or {}).get("amount") or
            r.get("totalPrice") or 9e9))
        price = float((chosen.get("price") or {}).get("amount")
                      or chosen.get("totalPrice") or 0)
        return {"success": True, "price": price,
                "error_message": False, "warning_message": False}

    def nshift_send_shipping(self, pickings):
        self.ensure_one()
        client = self._nshift_get_client()
        results = []
        for picking in pickings:
            results.append(self._nshift_book(client, picking))
        return results

    def _nshift_book(self, client, picking):
        payload = self._nshift_payload_from_picking(picking)
        if not payload["parcels"]:
            raise UserError(_("No parcels to ship for %s.") % picking.name)
        shipment = client.create_shipment(payload, picking=picking)
        shipment_id = shipment.get("id") or shipment.get("shipmentNo")
        if not shipment_id:
            raise UserError(_(
                "nShift returned no shipment id: %s") % shipment)

        # Confirm + print label
        confirmed = client.confirm_shipment(shipment_id, picking=picking)
        tracking_number = (confirmed.get("trackingNo") or
                           confirmed.get("parcels", [{}])[0].get("trackingNo")
                           or shipment.get("trackingNo") or "")

        # Fetch the PDF label
        try:
            pdf_bytes = client.get_pdf(shipment_id, picking=picking)
            self.env["ir.attachment"].create({
                "name": "nShift - %s.pdf" % picking.name,
                "type": "binary",
                "datas": __import__("base64").b64encode(pdf_bytes),
                "res_model": "stock.picking",
                "res_id": picking.id,
                "mimetype": "application/pdf",
            })
        except ShippingApiError as e:
            picking.message_post(
                body=_("Could not fetch nShift label: %s") % e)

        picking.write({
            "carrier_tracking_ref": tracking_number,
            "nshift_shipment_id": shipment_id,
            "nshift_tracking_number": tracking_number,
            "shipping_state": "ordered",
            "shipping_integration": "nshift",
        })
        picking.message_post(body=_(
            "nShift booking created: shipment %s, tracking %s") % (
            shipment_id, tracking_number or "—"))

        return {"exact_price": 0.0,  # nShift doesn't always return price on book
                "tracking_number": tracking_number}

    def nshift_get_tracking_link(self, picking):
        if not picking.nshift_tracking_number:
            return False
        # Generic nShift tracking portal
        return ("https://tracking.nshift.com/?id=%s" %
                picking.nshift_tracking_number)

    def nshift_cancel_shipment(self, picking):
        if not picking.nshift_shipment_id:
            return True
        client = self._nshift_get_client()
        ok = client.cancel_shipment(picking.nshift_shipment_id, picking=picking)
        if ok:
            picking.write({"shipping_state": "cancelled",
                           "carrier_tracking_ref": False})
            picking.message_post(body=_("nShift booking cancelled."))
        return ok

    def action_nshift_test_credentials(self):
        self.ensure_one()
        client = self._nshift_get_client()
        try:
            carriers = client.list_carriers()
        except ShippingApiError as e:
            raise UserError(str(e))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("nShift OK"),
                "message": _("Connected — %d carriers available") %
                           (len(carriers) if isinstance(carriers, list) else 0),
                "type": "success",
            },
        }
