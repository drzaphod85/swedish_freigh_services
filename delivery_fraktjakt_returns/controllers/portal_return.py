# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class FraktjaktPortalReturn(http.Controller):

    @http.route(["/my/fraktjakt/return/<int:picking_id>"],
                type="http", auth="user", website=True, methods=["POST"],
                csrf=True)
    def request_return(self, picking_id, **post):
        Picking = request.env["stock.picking"]
        picking = Picking.browse(picking_id).sudo().exists()
        partner = request.env.user.partner_id.commercial_partner_id
        if not picking or picking.partner_id.commercial_partner_id != partner:
            return request.redirect("/my")
        wizard = request.env["fraktjakt.return.wizard"].sudo().create({
            "picking_id": picking.id,
            "reason": "RETURN",
            "note": post.get("reason", ""),
        })
        try:
            wizard.action_create_return()
        except Exception:
            return request.render(
                "delivery_fraktjakt_returns.return_failure",
                {"picking": picking})
        return request.render(
            "delivery_fraktjakt_returns.return_success",
            {"picking": picking})
