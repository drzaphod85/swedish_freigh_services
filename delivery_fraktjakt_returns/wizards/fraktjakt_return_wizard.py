# -*- coding: utf-8 -*-
"""
Wizard that creates a return shipment at Fraktjakt.

Uses the return_link returned by the Order API — it creates a mirrored
shipment where the address is swapped from sender to customer.
"""
import logging

import requests

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class FraktjaktReturnWizard(models.TransientModel):
    _name = "fraktjakt.return.wizard"
    _description = "Create return via Fraktjakt"

    picking_id = fields.Many2one("stock.picking", required=True,
                                 ondelete="cascade")
    reason = fields.Selection(
        [("RETURN", "Return"),
         ("REPAIR", "Repair"),
         ("SAMPLE", "Sample")],
        default="RETURN", required=True)
    note = fields.Text(string="Message to customer")

    def action_create_return(self):
        self.ensure_one()
        picking = self.picking_id
        if not picking.fraktjakt_return_link:
            raise UserError(_(
                "No return link available for %s. This may be because the "
                "shipment is not yet paid, or because the Fraktjakt booking "
                "has no return_link.") % picking.name)

        try:
            resp = requests.get(picking.fraktjakt_return_link, timeout=20)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise UserError(_("Fraktjakt return failed: %s") % e)

        # Fraktjakt's return_link returns HTML with a link to the new
        # shipment. We don't parse HTML here — we log and point the user
        # to access_link so they can complete the purchase.
        picking.message_post(body=_(
            "Return created at Fraktjakt. Complete payment at "
            "<a href='%s' target='_blank'>Fraktjakt's portal</a>.") %
            picking.fraktjakt_access_link)

        # Email the customer with return instructions
        template = self.env.ref(
            "delivery_fraktjakt.mail_template_fraktjakt_shipped",
            raise_if_not_found=False)
        if template:
            template.send_mail(picking.id, force_send=False)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Return created"),
                "message": _("Logged on %s. Complete at Fraktjakt.") %
                           picking.name,
                "type": "success",
            },
        }
