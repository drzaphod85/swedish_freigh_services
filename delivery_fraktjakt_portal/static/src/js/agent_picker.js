/** @odoo-module **/
/* eslint-disable */

/**
 * Fraktjakt service point picker for the website_sale checkout.
 *
 * Triggered when the customer selects a Fraktjakt carrier. Fetches the
 * nearest service points via /fraktjakt/service_points and lets the
 * customer click to select one.
 */
(function () {
    'use strict';

    function rpc(url, params) {
        return fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                jsonrpc: '2.0',
                method: 'call',
                params: params || {}
            })
        }).then(function (r) { return r.json(); });
    }

    function renderAgents(agents) {
        var list = document.getElementById('fj_agent_list');
        if (!list) return;
        list.innerHTML = '';
        agents.forEach(function (a) {
            var col = document.createElement('div');
            col.className = 'col-md-6 mb-2';
            col.innerHTML =
                '<label class="card p-2 cursor-pointer">' +
                '<input type="radio" name="fj_agent" class="me-2" value="' + a.id + '"/>' +
                '<strong>' + (a.name || '') + '</strong><br/>' +
                '<small>' + (a.address || '') + ', ' +
                (a.postal_code || '') + ' ' + (a.city || '') + '</small><br/>' +
                '<small class="text-muted">' +
                (a.shipper_name || '') + ' — ' + (a.distance || '?') + ' m</small>' +
                '</label>';
            col.querySelector('input').addEventListener('change', function () {
                document.getElementById('fj_selected_agent').value = a.id;
                rpc('/fraktjakt/select_agent', {agent_id: a.id});
            });
            list.appendChild(col);
        });
    }

    function refreshAgents() {
        var picker = document.getElementById('fraktjakt_agent_picker');
        if (!picker) return;
        var zipInput = document.querySelector('input[name="zip"]');
        var countryInput = document.querySelector('select[name="country_id"] option:checked');
        var zip = zipInput ? zipInput.value : '';
        var country = countryInput ? countryInput.dataset.code || 'SE' : 'SE';
        if (!zip) return;
        rpc('/fraktjakt/service_points', {
            postal_code: zip,
            country_code: country
        }).then(function (resp) {
            if (resp && resp.result && resp.result.agents) {
                renderAgents(resp.result.agents);
            }
        });
    }

    document.addEventListener('DOMContentLoaded', refreshAgents);
    document.addEventListener('change', function (ev) {
        if (ev.target.matches('input[name="delivery_type"]') ||
            ev.target.matches('input[name="zip"]')) {
            refreshAgents();
        }
    });
})();
