# -*- coding: utf-8 -*-
"""
Extend the customer portal with Fraktjakt tracking.
"""
from odoo import http
from odoo.http import request


class FraktjaktPortal(http.Controller):

    @http.route(["/my/fraktjakt/picking/<int:picking_id>"],
                type="http", auth="user", website=True)
    def portal_picking_detail(self, picking_id, **kw):
        """Detail page for a specific shipment."""
        Picking = request.env["stock.picking"]
        picking = Picking.browse(picking_id).sudo().exists()
        # Security check: customer must match the order's partner
        partner = request.env.user.partner_id.commercial_partner_id
        if not picking or picking.partner_id.commercial_partner_id != partner:
            return request.redirect("/my")
        return request.render(
            "delivery_fraktjakt_portal.portal_picking_detail",
            {"picking": picking, "page_name": "fraktjakt_picking"})

    @http.route(["/my/fraktjakt/refresh/<int:picking_id>"],
                type="json", auth="user")
    def refresh_tracking(self, picking_id, **kw):
        Picking = request.env["stock.picking"]
        picking = Picking.browse(picking_id).sudo().exists()
        partner = request.env.user.partner_id.commercial_partner_id
        if not picking or picking.partner_id.commercial_partner_id != partner:
            return {"ok": False}
        try:
            picking.action_fraktjakt_refresh_tracking()
        except Exception:
            return {"ok": False}
        return {
            "ok": True,
            "state": picking.fraktjakt_state,
            "last_event": picking.fraktjakt_last_event,
        }
