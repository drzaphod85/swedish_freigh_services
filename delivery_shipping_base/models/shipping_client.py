# -*- coding: utf-8 -*-
"""
Abstract base class for shipping integration clients.

Handles:
- HTTP retry and timeouts
- Rate-limit respect (HTTP 429 backoff)
- Logging to shipping.api.log
- Standardized error handling
"""
import json
import logging
import time

import requests

from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
LOG_BODY_LIMIT = 65000


class ShippingApiError(UserError):
    """Raised when a carrier returns an error meant to be shown to the user."""


class ShippingClient:
    """Base for all carrier clients. Inherit and implement the methods
    that should exist (`rate`, `book`, `label`, `track`)."""

    #: Identifies which integration is logging (set by subclass)
    integration_name = "shipping"

    def __init__(self, env=None, log_model="shipping.api.log",
                 timeout=DEFAULT_TIMEOUT, debug=False):
        self.env = env
        self._log_model = log_model
        self._timeout = timeout
        self._debug = debug

    # ------------------------------------------------------------------
    # Low-level call
    # ------------------------------------------------------------------
    def _request(self, method, url, *, headers=None, params=None,
                 data=None, json_body=None, picking=None,
                 max_retries=MAX_RETRIES):
        """Generic HTTP call with retry and logging."""
        last_err = None
        last_resp = None
        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.request(
                    method, url,
                    headers=headers, params=params,
                    data=data, json=json_body,
                    timeout=self._timeout)
                last_resp = resp

                if resp.status_code == 429:
                    # Rate limit. Let the subclass read Retry-After.
                    wait = self._compute_backoff(resp, attempt)
                    _logger.warning(
                        "%s rate-limit (HTTP 429), waiting %.1f s",
                        self.integration_name, wait)
                    time.sleep(wait)
                    continue
                if resp.status_code in (502, 503, 504) and attempt < max_retries:
                    time.sleep(min(2 ** attempt, 8))
                    continue

                self._log_call(method, url, headers, data or json_body,
                               resp.text, resp.status_code, picking=picking)
                return resp
            except requests.RequestException as e:
                last_err = e
                _logger.warning("%s network error %s/%s: %s",
                                self.integration_name, attempt, max_retries, e)
                if attempt < max_retries:
                    time.sleep(1)

        # All attempts failed — log and raise
        self._log_call(method, url, headers, data or json_body,
                       last_resp.text if last_resp else "",
                       last_resp.status_code if last_resp else 0,
                       error=str(last_err) if last_err else "",
                       picking=picking)
        raise ShippingApiError(_(
            "Could not reach %s: %s") % (self.integration_name,
                                          last_err or "Empty response"))

    @staticmethod
    def _compute_backoff(resp, attempt):
        """Default backoff: use Retry-After header if present, otherwise
        exponential."""
        retry_after = resp.headers.get("Retry-After") if resp else None
        if retry_after:
            try:
                return float(retry_after)
            except (TypeError, ValueError):
                pass
        return min(2 ** attempt, 10)

    def _log_call(self, method, url, headers, body, response_body,
                  http_status, error=None, picking=None):
        if not (self.env and self._log_model):
            return
        try:
            request_text = self._stringify(body)
            if isinstance(headers, dict):
                # Mask sensitive headers
                hdr = {k: ("***" if k.lower() in ("authorization",
                                                  "x-api-key", "api-key")
                          else v) for k, v in headers.items()}
                request_text = ("HEADERS: %s\n\n%s" %
                                (json.dumps(hdr), request_text))
            self.env[self._log_model].sudo().create({
                "integration": self.integration_name,
                "endpoint": "%s %s" % (method, url),
                "http_status": http_status,
                "request_body": request_text[:LOG_BODY_LIMIT],
                "response_body": (response_body or "")[:LOG_BODY_LIMIT],
                "error": error or "",
                "picking_id": picking.id if picking else False,
            })
        except Exception:  # pragma: no cover — logging must never block flow
            _logger.exception("Failed to save shipping.api.log row")

    @staticmethod
    def _stringify(body):
        if body is None:
            return ""
        if isinstance(body, (dict, list)):
            return json.dumps(body, ensure_ascii=False, indent=2)
        if isinstance(body, bytes):
            try:
                return body.decode("utf-8", errors="replace")
            except Exception:
                return repr(body)
        return str(body)

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------
    def get(self, url, **kw):
        return self._request("GET", url, **kw)

    def post(self, url, **kw):
        return self._request("POST", url, **kw)

    def put(self, url, **kw):
        return self._request("PUT", url, **kw)

    def delete(self, url, **kw):
        return self._request("DELETE", url, **kw)

    @staticmethod
    def parse_json_or_raise(resp):
        """Try to read JSON. Raise ShippingApiError on failure."""
        if not resp.ok:
            try:
                payload = resp.json()
            except ValueError:
                payload = resp.text
            raise ShippingApiError(_(
                "HTTP %s: %s") % (resp.status_code, payload))
        try:
            return resp.json()
        except ValueError:
            raise ShippingApiError(_(
                "Expected JSON but received: %s") % resp.text[:500])
