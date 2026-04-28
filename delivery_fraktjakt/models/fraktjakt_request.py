# -*- coding: utf-8 -*-
"""
Fraktjakt API client
====================

Encapsulates all communication with Fraktjakt's XML API (v4.10).
- Builds XML payloads via xml.etree.ElementTree
- Handles URL encoding and MD5 checksum for caching
- Backoff on HTTP 429 (rate limit: 120/min, sliding 10/5s)
- Logs every call to the shipping.api.log model

API URL: https://api.fraktjakt.se
Test mode is configured per integration in Fraktjakt's UI.
"""
import base64
import hashlib
import logging
import time
from xml.etree import ElementTree as ET

import requests

from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

API_BASE_URL = "https://api.fraktjakt.se"
API_VERSION = "4.10.0"
DEFAULT_TIMEOUT = 30  # seconds

# Endpoints
ENDPOINTS = {
    "query": "/fraktjakt/query_xml",
    "requery": "/fraktjakt/requery_xml",
    "order": "/orders/order_xml",
    "shipment": "/shipments/shipment_xml",
    "trace": "/trace/xml_trace",
    "documents": "/shipping_documents/xml_get",
    "service_point_locator": "/service_points/locate_xml",
    "shipping_products": "/shipping_products/xml_list",
    "status": "/status/xml",
    "webshops": "/webshops/register_xml",
}


class FraktjaktError(UserError):
    """Raised when Fraktjakt returns code=2 or an HTTP error."""


class FraktjaktClient:
    """Lightweight client without ORM dependency — usable both from Odoo
    models and standalone test scripts."""

    def __init__(self, consignor_id, consignor_key, currency="SEK",
                 language="sv", env=None, log_model=None):
        self.consignor_id = consignor_id
        self.consignor_key = consignor_key
        self.currency = currency
        self.language = language
        self.env = env
        self._log_model = log_model

    # ------------------------------------------------------------------
    # XML builders
    # ------------------------------------------------------------------
    def _consignor_block(self, system_name="Odoo", system_version="19.0",
                         module_version="1.0.0"):
        """Build the <consignor> element required in almost every call."""
        block = ET.Element("consignor")
        ET.SubElement(block, "id").text = str(self.consignor_id)
        ET.SubElement(block, "key").text = str(self.consignor_key)
        ET.SubElement(block, "currency").text = self.currency
        ET.SubElement(block, "language").text = self.language
        ET.SubElement(block, "encoding").text = "UTF-8"
        ET.SubElement(block, "api_version").text = API_VERSION
        ET.SubElement(block, "system_name").text = system_name
        ET.SubElement(block, "system_version").text = system_version
        ET.SubElement(block, "module_version").text = module_version
        return block

    @staticmethod
    def _add_address(parent, tag, address):
        """address: dict with street_address_1, street_address_2,
        postal_code, city_name, country_code, residential, language..."""
        if not address:
            return
        node = ET.SubElement(parent, tag)
        for key in ("street_address_1", "street_address_2", "street_address_3",
                    "postal_code", "city_name", "country_code", "residential",
                    "language", "instructions", "entry_code"):
            if address.get(key) not in (None, "", False):
                ET.SubElement(node, key).text = str(address[key])

    @staticmethod
    def _add_commodities(parent, commodities):
        if not commodities:
            return
        node = ET.SubElement(parent, "commodities")
        for c in commodities:
            cn = ET.SubElement(node, "commodity")
            for key in ("name", "description", "quantity", "quantity_units",
                        "weight", "length", "width", "height", "taric",
                        "country_of_manufacture", "unit_price", "currency",
                        "article_number", "shelf_position", "in_own_parcel",
                        "shipped", "dangerous_goods", "dangerous_goods_un_nr"):
                if c.get(key) not in (None, "", False):
                    ET.SubElement(cn, key).text = str(c[key])

    @staticmethod
    def _add_parcels(parent, parcels):
        if not parcels:
            return
        node = ET.SubElement(parent, "parcels")
        for p in parcels:
            pn = ET.SubElement(node, "parcel")
            for key in ("weight", "length", "width", "height"):
                if p.get(key) not in (None, "", False):
                    ET.SubElement(pn, key).text = str(p[key])
            if p.get("commodities"):
                FraktjaktClient._add_commodities(pn, p["commodities"])

    # ------------------------------------------------------------------
    # Low-level call
    # ------------------------------------------------------------------
    def _post(self, endpoint, xml_payload=None, params=None,
              max_retries=3, picking=None):
        """Run an HTTP call. On HTTP 429 backoff per sliding window."""
        url = API_BASE_URL + ENDPOINTS[endpoint]
        data = {}
        if xml_payload is not None:
            xml_str = ET.tostring(xml_payload, encoding="utf-8",
                                  xml_declaration=True).decode("utf-8")
            data["xml"] = xml_str
            data["md5_checksum"] = hashlib.md5(
                xml_str.encode("utf-8")).hexdigest()
        if params:
            data.update(params)

        attempt = 0
        last_err = None
        while attempt < max_retries:
            attempt += 1
            try:
                _logger.debug("Fraktjakt %s POST %s", endpoint, url)
                resp = requests.post(url, data=data, timeout=DEFAULT_TIMEOUT)
                if resp.status_code == 429:
                    # Rate limit. Sliding window 5s.
                    wait = min(2 ** attempt, 10)
                    _logger.warning(
                        "Fraktjakt rate-limit (HTTP 429), waiting %s s", wait)
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                self._log_call(endpoint, data.get("xml", ""), resp.text,
                               resp.status_code, picking=picking)
                return self._parse_response(resp.text)
            except requests.HTTPError as e:
                last_err = e
                self._log_call(endpoint, data.get("xml", ""),
                               getattr(resp, "text", ""),
                               getattr(resp, "status_code", 0),
                               error=str(e), picking=picking)
                break
            except requests.RequestException as e:
                last_err = e
                _logger.warning("Fraktjakt network error (attempt %s): %s",
                                attempt, e)
                time.sleep(1)
        raise FraktjaktError(_(
            "Could not reach Fraktjakt (%s): %s") % (endpoint, last_err))

    def _get(self, endpoint, params, picking=None):
        url = API_BASE_URL + ENDPOINTS[endpoint]
        try:
            resp = requests.get(url, params=params, timeout=DEFAULT_TIMEOUT)
            resp.raise_for_status()
            self._log_call(endpoint, str(params), resp.text,
                           resp.status_code, picking=picking)
            return self._parse_response(resp.text)
        except requests.RequestException as e:
            self._log_call(endpoint, str(params), getattr(resp, "text", ""),
                           getattr(resp, "status_code", 0), error=str(e),
                           picking=picking)
            raise FraktjaktError(_(
                "Could not reach Fraktjakt (%s): %s") % (endpoint, e))

    @staticmethod
    def _parse_response(xml_text):
        """Parse the XML response and raise on code=2."""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            raise FraktjaktError(_(
                "Could not parse Fraktjakt response: %s\n\n%s") % (e, xml_text))
        code = (root.findtext("code") or "0").strip()
        status = (root.findtext("status") or "").strip()
        warning = (root.findtext("warning_message") or "").strip()
        error = (root.findtext("error_message") or "").strip()
        if code == "2" or status == "error":
            raise FraktjaktError(_(
                "Fraktjakt returned an error: %s") % (error or xml_text))
        if warning:
            _logger.info("Fraktjakt warning: %s", warning)
        return root

    def _log_call(self, endpoint, request_body, response_body, http_status,
                  error=None, picking=None):
        """Save the call to shipping.api.log if env is available."""
        if not (self.env and self._log_model):
            return
        try:
            self.env[self._log_model].sudo().create({
                "integration": "fraktjakt",
                "endpoint": endpoint,
                "http_status": http_status,
                "request_body": request_body[:65000] if request_body else "",
                "response_body": response_body[:65000] if response_body else "",
                "error": error or "",
                "picking_id": picking.id if picking else False,
            })
        except Exception:  # logging must never block flow
            _logger.exception("Failed to save shipping.api.log row")

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------
    def query(self, address_to, commodities=None, parcels=None,
              address_from=None, shipping_product_id=None, value=None,
              callback_url=None, reference=None, no_agents=False,
              cold=False, frozen=False, express=False, picking=None,
              extra_tags=None):
        """Query API — search shipping options.

        Returns list[dict] with shipping_products: id, name, description,
        price (incl. tax), tax, time_minutes, time_guarantee, agent_info...
        """
        shipment = ET.Element("shipment")
        shipment.append(self._consignor_block())
        if value is not None:
            ET.SubElement(shipment, "value").text = str(value)
        if callback_url:
            ET.SubElement(shipment, "callback_url").text = callback_url
        if reference:
            ET.SubElement(shipment, "reference").text = reference
        if shipping_product_id:
            ET.SubElement(shipment, "shipping_product_id").text = \
                str(shipping_product_id)
        if no_agents:
            ET.SubElement(shipment, "no_agents").text = "1"
        if cold:
            ET.SubElement(shipment, "cold").text = "1"
        if frozen:
            ET.SubElement(shipment, "frozen").text = "1"
        if express:
            ET.SubElement(shipment, "express").text = "1"
        if extra_tags:
            tags = ET.SubElement(shipment, "tags")
            for t in extra_tags:
                ET.SubElement(tags, "tag").text = t
        self._add_commodities(shipment, commodities)
        self._add_parcels(shipment, parcels)
        self._add_address(shipment, "address_to", address_to)
        self._add_address(shipment, "address_from", address_from)

        root = self._post("query", shipment, picking=picking)
        return self._parse_query_response(root)

    @staticmethod
    def _parse_query_response(root):
        result = {
            "shipment_id": root.findtext("id") or root.findtext("shipment_id"),
            "access_link": root.findtext("access_link"),
            "currency": root.findtext("currency") or "SEK",
            "products": [],
        }
        for sp in root.findall(".//shipping_product"):
            product = {
                "id": sp.findtext("id"),
                "name": sp.findtext("name") or sp.findtext("description"),
                "description": sp.findtext("description"),
                "price": float(sp.findtext("price") or 0),
                "tax": float(sp.findtext("tax") or 0),
                "tax_class": sp.findtext("tax_class") or "",
                "time_minutes": sp.findtext("time_minutes"),
                "time_guarantee": sp.findtext("time_guarantee"),
                "arrival_time": sp.findtext("arrival_time"),
                "arrival_days": sp.findtext("arrival_days"),
                "agent_info": sp.findtext("agent_info"),
                "agent_link": sp.findtext("agent_selection_link"),
                "shipper": {
                    "id": sp.findtext("shipper/id"),
                    "name": sp.findtext("shipper/name"),
                    "logo_url": sp.findtext("shipper/logo_url"),
                },
            }
            result["products"].append(product)
        return result

    def order(self, shipment_id, sender=None, recipient=None,
              shipping_product_id=None, agent_id=None, no_agents=False,
              callback_url=None, reference=None, message_to=None,
              export_reason=None, picking=None):
        """Order API type 1 — book shipping based on a shipment_id from Query."""
        order_node = ET.Element("OrderSpecification")
        order_node.append(self._consignor_block())
        ET.SubElement(order_node, "shipment_id").text = str(shipment_id)
        if shipping_product_id:
            ET.SubElement(order_node, "shipping_product_id").text = \
                str(shipping_product_id)
        if agent_id:
            ET.SubElement(order_node, "agent_id").text = str(agent_id)
        if no_agents:
            ET.SubElement(order_node, "no_agents").text = "1"
        if callback_url:
            ET.SubElement(order_node, "callback_url").text = callback_url
        if reference:
            ET.SubElement(order_node, "reference").text = reference
        if message_to:
            ET.SubElement(order_node, "message_to").text = message_to
        if export_reason:
            ET.SubElement(order_node, "export_reason").text = export_reason
        self._add_party(order_node, "sender", sender)
        self._add_party(order_node, "recipient", recipient)

        root = self._post("order", order_node, picking=picking)
        return {
            "shipment_id": root.findtext("shipment_id"),
            "access_code": root.findtext("access_code"),
            "access_link": root.findtext("access_link"),
            "tracking_code": root.findtext("tracking_code"),
            "tracking_link": root.findtext("tracking_link"),
            "tracking_number": root.findtext("tracking_number"),
            "amount": float(root.findtext("amount") or 0),
            "currency": root.findtext("currency") or "SEK",
            "agent_selection_link": root.findtext("agent_selection_link"),
            "return_link": root.findtext("return_link"),
            "cancel_link": root.findtext("cancel_link"),
        }

    @staticmethod
    def _add_party(parent, tag, party):
        if not party:
            return
        node = ET.SubElement(parent, tag)
        for key in ("company", "name_to", "telephone_to", "email_to",
                    "fax_to", "tax_id", "eori", "ioss", "voec", "gb_vat",
                    "mva_num", "rex"):
            if party.get(key) not in (None, "", False):
                ET.SubElement(node, key).text = str(party[key])
        if party.get("address"):
            FraktjaktClient._add_address(node, "address", party["address"])

    def shipment(self, shipping_product_id, address_to, sender=None,
                 commodities=None, parcels=None, address_from=None,
                 callback_url=None, reference=None, message_to=None,
                 agent_id=None, value=None, export_reason=None, picking=None):
        """Shipment API — create a direct booking without a prior Query."""
        ship = ET.Element("shipment")
        ship.append(self._consignor_block())
        ET.SubElement(ship, "shipping_product_id").text = str(shipping_product_id)
        if value is not None:
            ET.SubElement(ship, "value").text = str(value)
        if callback_url:
            ET.SubElement(ship, "callback_url").text = callback_url
        if reference:
            ET.SubElement(ship, "reference").text = reference
        if message_to:
            ET.SubElement(ship, "message_to").text = message_to
        if agent_id:
            ET.SubElement(ship, "agent_id").text = str(agent_id)
        if export_reason:
            ET.SubElement(ship, "export_reason").text = export_reason
        self._add_party(ship, "sender", sender)
        self._add_commodities(ship, commodities)
        self._add_parcels(ship, parcels)
        self._add_address(ship, "address_to", address_to)
        self._add_address(ship, "address_from", address_from)

        root = self._post("shipment", ship, picking=picking)
        return {
            "shipment_id": root.findtext("shipment_id"),
            "access_code": root.findtext("access_code"),
            "access_link": root.findtext("access_link"),
            "tracking_code": root.findtext("tracking_code"),
            "tracking_link": root.findtext("tracking_link"),
            "tracking_number": root.findtext("tracking_number"),
            "amount": float(root.findtext("amount") or 0),
            "currency": root.findtext("currency") or "SEK",
            "agent_selection_link": root.findtext("agent_selection_link"),
        }

    def trace(self, shipment_id, locale="sv", picking=None):
        """Track & Trace API — retrieve status. Called via GET."""
        params = {
            "consignor_id": self.consignor_id,
            "consignor_key": self.consignor_key,
            "shipment_id": shipment_id,
            "locale": locale,
        }
        root = self._get("trace", params, picking=picking)
        events = []
        for e in root.findall(".//tracking_event") + root.findall(".//state"):
            events.append({
                "timestamp": e.findtext("timestamp") or e.findtext("time"),
                "description": e.findtext("description")
                                or e.findtext("event_description"),
                "location": e.findtext("location"),
                "code": e.findtext("code") or e.findtext("state_code"),
            })
        return {
            "tracking_code": root.findtext("tracking_code"),
            "tracking_number": root.findtext("tracking_number"),
            "tracking_link": root.findtext("tracking_link"),
            "shipper_name": root.findtext("shipper_name")
                            or root.findtext(".//shipper/name"),
            "current_state": root.findtext("state") or root.findtext("status"),
            "current_state_description": root.findtext("state_description"),
            "events": events,
        }

    def shipping_documents(self, shipment_id, locale="sv", picking=None):
        """Shipping Documents API — retrieve the label as Base64.

        Returns a list of {name, type_id, type_name, file (bytes)}.
        """
        params = {
            "consignor_id": self.consignor_id,
            "consignor_key": self.consignor_key,
            "shipment_id": shipment_id,
            "locale": locale,
        }
        root = self._get("documents", params, picking=picking)
        docs = []
        for d in root.findall(".//shipping_document"):
            file_b64 = d.findtext("file") or ""
            try:
                file_bytes = base64.b64decode(file_b64) if file_b64 else b""
            except Exception:
                file_bytes = b""
            docs.append({
                "name": d.findtext("name") or "fraktjakt_document.pdf",
                "type_id": d.findtext("type_id"),
                "type_name": d.findtext("type_name"),
                "type_description": d.findtext("type_description"),
                "state_name": d.findtext("state_name"),
                "format_name": d.findtext("format_name"),
                "file_b64": file_b64,
                "file_bytes": file_bytes,
            })
        return docs

    def service_point_locator(self, postal_code, country_code="SE",
                              shipper_id=None, street_address=None,
                              limit=10, picking=None):
        """Service Point Locator API — find nearest service points."""
        body = ET.Element("service_point_request")
        body.append(self._consignor_block())
        ET.SubElement(body, "postal_code").text = postal_code
        ET.SubElement(body, "country_code").text = country_code
        if shipper_id:
            ET.SubElement(body, "shipper_id").text = str(shipper_id)
        if street_address:
            ET.SubElement(body, "street_address").text = street_address
        ET.SubElement(body, "limit").text = str(limit)

        root = self._post("service_point_locator", body, picking=picking)
        agents = []
        for a in root.findall(".//service_point") + root.findall(".//agent"):
            agents.append({
                "id": a.findtext("id"),
                "shipper_internal_id": a.findtext("shipper_internal_id"),
                "name": a.findtext("name"),
                "address": a.findtext("street_address")
                           or a.findtext("address"),
                "postal_code": a.findtext("postal_code"),
                "city": a.findtext("city_name") or a.findtext("city"),
                "distance": a.findtext("distance"),
                "latitude": a.findtext("latitude"),
                "longitude": a.findtext("longitude"),
                "opening_hours": a.findtext("opening_hours"),
                "shipper_name": a.findtext("shipper_name")
                                or a.findtext("shipper/name"),
                "shipper_id": a.findtext("shipper/id"),
            })
        return agents

    def shipping_products(self, picking=None):
        """Shipping Products API — list all shipping_products available
        to this integration."""
        params = {
            "consignor_id": self.consignor_id,
            "consignor_key": self.consignor_key,
        }
        root = self._get("shipping_products", params, picking=picking)
        products = []
        for sp in root.findall(".//shipping_product"):
            products.append({
                "id": sp.findtext("id"),
                "name": sp.findtext("name") or sp.findtext("description"),
                "shipper_name": sp.findtext("shipper_name")
                                or sp.findtext(".//shipper/name"),
                "shipper_id": sp.findtext("shipper_id")
                              or sp.findtext(".//shipper/id"),
            })
        return products

    def status(self):
        """Status API — check Fraktjakt servers and connected carriers.
        Useful for fallback logic."""
        params = {
            "consignor_id": self.consignor_id,
            "consignor_key": self.consignor_key,
        }
        root = self._get("status", params)
        return {
            "server_status": root.findtext("server_status") or "ok",
            "code": root.findtext("code") or "0",
            "message": root.findtext("message"),
        }
