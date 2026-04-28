# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


FJ_STATES = [
    ("draft", "Not Booked"),
    ("queried", "Quote Requested"),
    ("ordered", "Booked at Fraktjakt"),
    ("paid", "Paid (ready to ship)"),
    ("in_transit", "In Transit"),
    ("at_agent", "At Service Point"),
    ("delivered", "Delivered"),
    ("returned", "Returned"),
    ("cancelled", "Cancelled"),
    ("error", "Error"),
]


class StockPicking(models.Model):
    _inherit = "stock.picking"

    # Identifiers at Fraktjakt
    fraktjakt_shipment_id = fields.Char(string="Fraktjakt shipment ID",
                                        copy=False, readonly=True, index=True)
    fraktjakt_access_code = fields.Char(string="Access code",
                                        copy=False, readonly=True)
    fraktjakt_access_link = fields.Char(string="Manage at Fraktjakt",
                                        copy=False, readonly=True)
    fraktjakt_tracking_code = fields.Char(string="Tracking code",
                                          copy=False, readonly=True)
    fraktjakt_tracking_number = fields.Char(string="Tracking number",
                                            copy=False, readonly=True)
    fraktjakt_tracking_link = fields.Char(string="Tracking link",
                                          copy=False, readonly=True)
    fraktjakt_amount = fields.Monetary(string="Shipping cost",
                                       currency_field="fraktjakt_currency_id",
                                       copy=False, readonly=True)
    fraktjakt_currency = fields.Char(string="Currency", copy=False, readonly=True)
    fraktjakt_currency_id = fields.Many2one(
        "res.currency",
        compute="_compute_fraktjakt_currency_id",
        string="Currency",
    )
    fraktjakt_return_link = fields.Char(string="Create return",
                                        copy=False, readonly=True)
    fraktjakt_cancel_link = fields.Char(string="Cancellation link",
                                        copy=False, readonly=True)
    # fraktjakt_state is Fraktjakt-specific. We mirror it to generic
    # shipping_state via the write override so admin views in the base
    # module also see status.
    fraktjakt_state = fields.Selection(FJ_STATES, default="draft",
                                       string="Fraktjakt status",
                                       copy=False, tracking=True)
    fraktjakt_agent_id = fields.Char(string="Selected service point",
                                     help="Fraktjakt agent_id if the customer "
                                          "selected a service point at "
                                          "checkout.")
    # Backwards-compatible aliases to generic shipping_last_event* fields.
    fraktjakt_last_event = fields.Char(related="shipping_last_event",
                                       readonly=False)
    fraktjakt_last_event_at = fields.Datetime(related="shipping_last_event_at",
                                              readonly=False)

    @api.depends("fraktjakt_currency")
    def _compute_fraktjakt_currency_id(self):
        Currency = self.env["res.currency"]
        for rec in self:
            rec.fraktjakt_currency_id = Currency.search(
                [("name", "=", rec.fraktjakt_currency or "SEK")], limit=1)

    def write(self, vals):
        """Sync shipping_state ↔ fraktjakt_state and set integration."""
        if "fraktjakt_state" in vals and "shipping_state" not in vals:
            vals["shipping_state"] = vals["fraktjakt_state"]
        if "shipping_state" in vals and "fraktjakt_state" not in vals:
            # Only if it's a Fraktjakt picking (otherwise leave alone)
            for rec in self:
                if rec.shipping_integration == "fraktjakt" or \
                        rec.fraktjakt_shipment_id:
                    vals["fraktjakt_state"] = vals["shipping_state"]
                    break
        if vals.get("fraktjakt_shipment_id") and \
                not vals.get("shipping_integration"):
            vals["shipping_integration"] = "fraktjakt"
        return super().write(vals)

    # Button: refresh tracking manually
    def action_fraktjakt_refresh_tracking(self):
        for picking in self:
            if not picking.fraktjakt_shipment_id:
                continue
            client = picking.carrier_id._fraktjakt_get_client()
            data = client.trace(picking.fraktjakt_shipment_id,
                                locale=(self.env.lang or "sv")[:2],
                                picking=picking)
            picking.write({
                "fraktjakt_tracking_code":
                    data["tracking_code"] or picking.fraktjakt_tracking_code,
                "fraktjakt_tracking_link":
                    data["tracking_link"] or picking.fraktjakt_tracking_link,
                "fraktjakt_tracking_number":
                    data["tracking_number"]
                    or picking.fraktjakt_tracking_number,
                "fraktjakt_last_event": data.get("current_state_description")
                                        or data.get("current_state") or "",
            })
            for ev in data["events"]:
                picking.message_post(body=_(
                    "Status: %s — %s") % (ev.get("description") or "",
                                          ev.get("location") or ""))
        return True

    def action_fraktjakt_open_dashboard(self):
        self.ensure_one()
        if not self.fraktjakt_access_link:
            raise UserError(_(
                "No Fraktjakt link available yet — book the shipment first."))
        return {
            "type": "ir.actions.act_url",
            "target": "new",
            "url": self.fraktjakt_access_link,
        }

    @api.model
    def _fraktjakt_cron_poll_tracking(self):
        """Backup cron: fetch status for shipments that are not yet finished."""
        pickings = self.search([
            ("carrier_id.delivery_type", "=", "fraktjakt"),
            ("fraktjakt_shipment_id", "!=", False),
            ("fraktjakt_state", "in",
             ["ordered", "paid", "in_transit", "at_agent"]),
        ], limit=200)
        for picking in pickings:
            try:
                picking.action_fraktjakt_refresh_tracking()
            except Exception as e:  # log and continue
                picking.message_post(
                    body=_("Fraktjakt poll failed: %s") % e)
        return True
