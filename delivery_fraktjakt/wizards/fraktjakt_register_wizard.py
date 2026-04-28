# -*- coding: utf-8 -*-
"""
Wizard to register a new Fraktjakt account via the Webshops API.
Creates a company + integration at Fraktjakt and returns
consignor_id/consignor_key, which are saved on res.company.
"""
import logging
import secrets
from xml.etree import ElementTree as ET

import requests

from odoo import _, fields, models
from odoo.exceptions import UserError

from ..models.fraktjakt_request import API_BASE_URL, ENDPOINTS, API_VERSION

_logger = logging.getLogger(__name__)


class FraktjaktRegisterWizard(models.TransientModel):
    _name = "fraktjakt.register.wizard"
    _description = "Register Fraktjakt account"

    mode = fields.Selection(
        [("import", "Paste existing credentials"),
         ("register", "Register new account via Fraktjakt")],
        default="import", required=True)

    company_id = fields.Many2one("res.company", required=True,
                                 default=lambda self: self.env.company)

    # Import mode
    consignor_id = fields.Char(string="Consignor ID")
    consignor_key = fields.Char(string="Consignor Key")

    # Registration mode
    user_email = fields.Char(string="Email")
    user_password = fields.Char(string="Password")
    company_name = fields.Char(string="Company name")
    org_no = fields.Char(string="Organization number")
    street = fields.Char(string="Street address")
    zip = fields.Char(string="Postal code")
    city = fields.Char(string="City")
    phone = fields.Char(string="Phone")
    country_code = fields.Char(default="SE", required=True)

    def action_apply(self):
        self.ensure_one()
        if self.mode == "import":
            if not (self.consignor_id and self.consignor_key):
                raise UserError(_("Fill in both ID and Key."))
            self.company_id.write({
                "fraktjakt_consignor_id": self.consignor_id,
                "fraktjakt_consignor_key": self.consignor_key,
            })
        else:
            cid, ckey = self._register_via_api()
            self.company_id.write({
                "fraktjakt_consignor_id": cid,
                "fraktjakt_consignor_key": ckey,
            })

        # Generate webhook token if missing
        if not self.company_id.fraktjakt_callback_token:
            self.company_id.fraktjakt_callback_token = \
                secrets.token_urlsafe(32)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Fraktjakt ready"),
                "message": _("Credentials saved on %s") %
                           self.company_id.name,
                "type": "success",
            },
        }

    def _register_via_api(self):
        """POST to /webshops/register_xml."""
        body = ET.Element("webshop")
        ET.SubElement(body, "api_version").text = API_VERSION
        ET.SubElement(body, "user_email").text = self.user_email or ""
        ET.SubElement(body, "user_password").text = self.user_password or ""
        ET.SubElement(body, "company_name").text = self.company_name or ""
        ET.SubElement(body, "org_no").text = self.org_no or ""
        ET.SubElement(body, "street_address_1").text = self.street or ""
        ET.SubElement(body, "postal_code").text = self.zip or ""
        ET.SubElement(body, "city_name").text = self.city or ""
        ET.SubElement(body, "country_code").text = self.country_code or "SE"
        ET.SubElement(body, "telephone").text = self.phone or ""
        ET.SubElement(body, "system_name").text = "Odoo"
        ET.SubElement(body, "system_version").text = "19.0"

        xml = ET.tostring(body, encoding="utf-8",
                          xml_declaration=True).decode("utf-8")
        try:
            resp = requests.post(API_BASE_URL + ENDPOINTS["webshops"],
                                 data={"xml": xml}, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise UserError(_("Could not reach Fraktjakt: %s") % e)
        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError as e:
            raise UserError(_("Invalid XML from Fraktjakt: %s") % e)
        if (root.findtext("code") or "0") == "2":
            raise UserError(
                root.findtext("error_message") or _("Registration failed"))
        cid = root.findtext("consignor_id") or root.findtext(".//id")
        ckey = root.findtext("consignor_key") or root.findtext(".//key")
        if not (cid and ckey):
            raise UserError(_("Fraktjakt returned no credentials"))
        return cid, ckey
