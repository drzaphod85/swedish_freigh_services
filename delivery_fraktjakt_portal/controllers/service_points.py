# -*- coding: utf-8 -*-
"""
JSON endpoint that the checkout page calls to fetch nearby service points.
"""
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class FraktjaktServicePoints(http.Controller):

    @http.route("/fraktjakt/service_points", type="json", auth="public",
                methods=["POST"], csrf=False)
    def list_service_points(self, postal_code, country_code="SE",
                            shipper_id=None, street_address=None, **kw):
        """Return a list of service points near `postal_code`."""
        carrier = request.env["delivery.carrier"].sudo().search(
            [("delivery_type", "=", "fraktjakt"), ("active", "=", True)],
            limit=1)
        if not carrier:
            return {"agents": [], "error": "no_carrier"}
        try:
            client = carrier._fraktjakt_get_client()
            agents = client.service_point_locator(
                postal_code=postal_code,
                country_code=country_code,
                shipper_id=shipper_id,
                street_address=street_address)
        except Exception as e:
            _logger.warning("service_points error: %s", e)
            return {"agents": [], "error": str(e)}
        return {"agents": agents}

    @http.route("/fraktjakt/select_agent", type="json", auth="public",
                methods=["POST"], csrf=False)
    def select_agent(self, agent_id, **kw):
        """Save the selected service point on the current website_sale order."""
        order = request.website.sale_get_order() if hasattr(
            request, "website") else None
        if not order:
            return {"ok": False, "error": "no_order"}
        order.sudo().write({"fraktjakt_agent_id": agent_id})
        return {"ok": True}
