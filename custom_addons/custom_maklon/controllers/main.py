import hashlib
import hmac
import json
import logging
import time

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

PARAM_TOKEN = 'mazta.token'     # token (satu pasang untuk kedua arah)
PARAM_SECRET = 'mazta.secret'   # secret HMAC (satu pasang untuk kedua arah)


def _json(data, status=200):
    return request.make_json_response(data, status=status)


class MaklonController(http.Controller):

    def _verifikasi(self, body):
        """Token (Bearer) + tanda tangan HMAC-SHA256 atas '<timestamp>.<body>'.
        Kembalian: pesan galat (str) atau None kalau sah."""
        icp = request.env['ir.config_parameter'].sudo()
        token = (icp.get_param(PARAM_TOKEN) or '').strip()
        secret = (icp.get_param(PARAM_SECRET) or '').strip()
        if not token or not secret:
            return 'integrasi belum dikonfigurasi'
        hdr = request.httprequest.headers
        got = (hdr.get('Authorization') or '').replace('Bearer ', '', 1).strip()
        if not hmac.compare_digest(got, token):
            return 'token tidak valid'
        ts = (hdr.get('X-Timestamp') or '').strip()
        try:
            selisih = abs(time.time() - int(ts))
        except ValueError:
            return 'X-Timestamp tidak valid'
        if selisih > 300:
            return 'X-Timestamp kedaluwarsa'
        want = hmac.new(secret.encode('utf-8'), ts.encode('utf-8') + b'.' + body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest((hdr.get('X-Signature') or '').strip().lower(), want):
            return 'tanda tangan tidak valid'
        return None

    @http.route('/maklon/request', type='http', auth='public', methods=['POST'], csrf=False)
    def terima_request(self, **kw):
        """Mazta Finance -> Odoo: buat draft.maklon dari Request Maklon.
        Body JSON: {request_id, customer, sales}. Idempoten per request_id."""
        body = request.httprequest.get_data()
        galat = self._verifikasi(body)
        if galat:
            status = 503 if 'belum dikonfigurasi' in galat else 401
            return _json({'ok': False, 'error': galat}, status)
        try:
            data = json.loads(body.decode('utf-8'))
        except ValueError:
            return _json({'ok': False, 'error': 'isi bukan JSON'}, 400)
        rid = (data.get('request_id') or '').strip()
        customer = ' '.join((data.get('customer') or '').split())
        sales = ' '.join((data.get('sales') or '').split())
        if not rid or not customer:
            return _json({'ok': False, 'error': 'request_id dan customer wajib diisi'}, 400)

        Draft = request.env['draft.maklon'].sudo()
        ada = Draft.with_context(active_test=False).search([('finance_request_id', '=', rid)], limit=1)
        if ada:
            return _json({'ok': True, 'odoo_id': ada.id, 'duplikat': True})
        try:
            rec = Draft.create({
                'finance_request_id': rid,
                'finance_customer_name': customer,
                'finance_sales_name': sales,
            })
            rec.message_post(body='Request Maklon dari Mazta Finance %s — customer: %s — sales: %s' % (rid, customer, sales))
        except Exception as e:  # noqa: BLE001
            request.env.cr.rollback()
            _logger.info("Maklon request %s ditolak saat membuat draft: %s", rid, e)
            return _json({'ok': False, 'error': 'gagal membuat draft: %s' % str(e)[:200]}, 500)
        return _json({'ok': True, 'odoo_id': rec.id})
