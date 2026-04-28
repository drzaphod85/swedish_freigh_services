# -*- coding: utf-8 -*-
"""
Fraktjakt webhook receiver
==========================

Fraktjakt calls /fraktjakt/webhook/<token> with JSON whenever something
happens to a shipment (status changes, carrier reports tracking, label
becomes available).

Token validation: match against res.company.fraktjakt_callback_token.
Return HTTP 200 as soon as we received it, even if no matching picking
is found — otherwise Fraktjakt stops sending.
"""
import json
import logging
from datetime import datetime

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


# Mapping from Fraktjakt's state strings to our internal state values
STATE_MAP = {
    "draft": "draft",
    "saved": "draft",
    "queried": "queried",
    "ordered": "ordered",
    "paid": "paid",
    "in_transit": "in_transit",
    "in transit": "in_transit",
    "shipped": "in_transit",
    "delivered_to_agent": "at_agent",
    "at_agent": "at_agent",
    "at agent": "at_agent",
    "delivered": "delivered",
    "returned": "returned",
    "cancelled": "cancelled",
}


class FraktjaktWebhook(http.Controller):

    @http.route("/fraktjakt/webhook/<string:token>",
                type="json", auth="public", methods=["POST"], csrf=False)
    def webhook(self, token, **kwargs):
        company = request.env["res.company"].sudo().search(
            [("fraktjakt_callback_token", "=", token)], limit=1)
        if not company:
            _logger.warning("Fraktjakt webhook with unknown token: %s", token)
            return {"ok": False, "reason": "unknown_token"}

        try:
            payload = request.jsonrequest or json.loads(
                request.httprequest.data or b"{}")
        except Exception as e:
            _logger.warning("Fraktjakt webhook payload error: %s", e)
            return {"ok": False, "reason": "bad_payload"}

        shipment_id = str(payload.get("shipment_id")
                          or payload.get("id") or "")
        if not shipment_id:
            return {"ok": False, "reason": "no_shipment_id"}

        Picking = request.env["stock.picking"].sudo()
        picking = Picking.search(
            [("fraktjakt_shipment_id", "=", shipment_id),
             ("company_id", "=", company.id)], limit=1)
        if not picking:
            # Webhook for a shipment we don't know — log and acknowledge.
            _logger.info("Fraktjakt webhook for unknown shipment: %s",
                         shipment_id)
            return {"ok": True, "matched": False}

        # Extract interesting fields
        state_raw = (payload.get("state") or payload.get("status") or "").lower()
        new_state = STATE_MAP.get(state_raw, picking.fraktjakt_state)
        update = {"fraktjakt_state": new_state}

        if payload.get("tracking_number"):
            update["fraktjakt_tracking_number"] = payload["tracking_number"]
            update["carrier_tracking_ref"] = payload["tracking_number"]
        if payload.get("tracking_link"):
            update["fraktjakt_tracking_link"] = payload["tracking_link"]
        if payload.get("tracking_code"):
            update["fraktjakt_tracking_code"] = payload["tracking_code"]
        if payload.get("event_description"):
            update["fraktjakt_last_event"] = payload["event_description"]
            update["fraktjakt_last_event_at"] = datetime.utcnow()

        picking.write(update)

        # Attach any shipping documents that come with the callback
        for doc in (payload.get("shipping_documents") or []):
            file_b64 = doc.get("file") or doc.get("base64")
            if not file_b64:
                continue
            request.env["ir.attachment"].sudo().create({
                "name": "Fraktjakt - %s" % doc.get("name", "document.pdf"),
                "type": "binary",
                "datas": file_b64,
                "res_model": "stock.picking",
                "res_id": picking.id,
                "mimetype": "application/pdf",
            })

        # Create a chatter post for traceability
        body = "<b>Fraktjakt webhook:</b> %s" % (
            payload.get("event_description") or new_state)
        if payload.get("location"):
            body += " (%s)" % payload["location"]
        picking.message_post(body=body)

        return {"ok": True, "matched": True}
