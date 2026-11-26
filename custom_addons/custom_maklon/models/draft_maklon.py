import hashlib
import hmac
import json
import logging
import time

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

PARAM_BASE_URL = 'mazta.base_url'                 # mis. https://maztafinance.com
PARAM_CALLBACK_TOKEN = 'mazta.token'              # token (satu pasang untuk kedua arah)
PARAM_CALLBACK_SECRET = 'mazta.secret'           # secret HMAC (satu pasang untuk kedua arah)


class DraftMaklon(models.Model):
    _inherit = 'draft.maklon'

    # Kunci pencocokan dengan Request Maklon di Mazta Finance.
    # copy=False: draft hasil salinan bukan request itu lagi (kalau ikut tersalin, satu request punya dua MOU).
    finance_request_id = fields.Char(string="ID Request Mazta Finance", index=True, copy=False, readonly=True)
    finance_customer_name = fields.Char(
        string="Nama Customer (dari Mazta Finance)", copy=False,
        help="Nama yang diketik sales. Pilih Nama Pelanggan yang sesuai di kolom Nama Pelanggan.")
    finance_sales_name = fields.Char(string="Sales Pengaju (Mazta Finance)", copy=False, readonly=True)

    mazta_callback_state = fields.Selection(
        [('pending', 'Menunggu'), ('sent', 'Terkirim'), ('failed', 'Gagal')], string="Kabar ke Mazta Finance",
        copy=False, readonly=True)
    mazta_callback_error = fields.Char(string="Galat Kabar Mazta Finance", copy=False, readonly=True)
    mazta_callback_at = fields.Datetime(string="Waktu Kabar Mazta Finance", copy=False, readonly=True)

    def write(self, vals):
        res = super().write(vals)
        if vals.get('state') == 'mou':
            todo = self.filtered(lambda r: r.finance_request_id and r.mazta_callback_state != 'sent')
            if todo and all(self._mazta_konfigurasi()):
                # Tidak dikirim di sini: kirim lewat cron setelah transaksi ini commit, supaya tombol MOU
                # tidak menunggu jaringan dan kabar tidak terkirim bila transaksi dibatalkan.
                todo.sudo().write({'mazta_callback_state': 'pending'})
                cron = self.env.ref('custom_maklon.cron_kirim_ulang_mazta', raise_if_not_found=False)
                if cron:
                    cron.sudo()._trigger()
        return res

    # ------------------------------------------------------------------ callback
    def _mazta_konfigurasi(self):
        icp = self.env['ir.config_parameter'].sudo()
        base = (icp.get_param(PARAM_BASE_URL) or '').strip().rstrip('/')
        token = (icp.get_param(PARAM_CALLBACK_TOKEN) or '').strip()
        secret = (icp.get_param(PARAM_CALLBACK_SECRET) or '').strip()
        return base, token, secret

    def _mazta_kirim_callback(self):
        """Kirim kabar MOU jadi ke Mazta Finance (REST). Tidak pernah melempar galat —
        kegagalan dicatat di record dan dicoba ulang oleh cron."""
        self.ensure_one()
        base, token, secret = self._mazta_konfigurasi()
        if not (base and token and secret):
            # Parameter kosong (mis. build staging yang dinetralkan) = tidak mengirim.
            _logger.info("Maklon %s: parameter Mazta Finance kosong, kabar tidak dikirim.", self.draft_name)
            return False
        payload = {
            'request_id': self.finance_request_id,
            'status': 'mou_created',
            'mou_number': self.draft_name or '',
            'brand': self.brand or '',
            'customer': (self.nama_cust.display_name if self.nama_cust else self.finance_customer_name) or '',
        }
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        ts = str(int(time.time()))
        sig = hmac.new(secret.encode('utf-8'), ts.encode('utf-8') + b'.' + body, hashlib.sha256).hexdigest()
        url = '%s/api/integrasi/v1/maklon/%s/mou' % (base, self.finance_request_id)
        galat = ''
        try:
            resp = requests.post(url, data=body, timeout=15, headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token,
                'X-Timestamp': ts,
                'X-Signature': sig,
            })
            if resp.status_code == 200:
                self.sudo().write({
                    'mazta_callback_state': 'sent', 'mazta_callback_error': False,
                    'mazta_callback_at': fields.Datetime.now(),
                })
                return True
            galat = 'HTTP %s: %s' % (resp.status_code, (resp.text or '')[:200])
        except Exception as e:  # noqa: BLE001 - jaringan apa pun jangan menggagalkan konfirmasi MOU
            galat = str(e)[:250]
        _logger.info("Maklon %s: kabar ke Mazta Finance gagal (%s), akan dicoba ulang.", self.draft_name, galat)
        self.sudo().write({
            'mazta_callback_state': 'failed', 'mazta_callback_error': galat,
            'mazta_callback_at': fields.Datetime.now(),
        })
        return False

    def action_kirim_ulang_mazta(self):
        """Tombol 'Tarik Ulang': kirim lagi kabar MOU (termasuk yang sudah Terkirim), mis. karena penomoran MOU berubah."""
        records = self.filtered(lambda r: r.finance_request_id and r.state == 'mou')
        if not records:
            raise UserError(_("Hanya request Mazta Finance yang sudah berstatus MOU yang bisa ditarik ulang."))
        base, token, secret = self._mazta_konfigurasi()
        if not (base and token and secret):
            raise UserError(_("Alamat, token, dan secret Mazta Finance belum diisi di System Parameters."))
        ok = sum(1 for rec in records if rec._mazta_kirim_callback())
        failed = len(records) - ok
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Tarik Ulang ke Mazta Finance"),
                'message': _("Terkirim: %(ok)s. Gagal: %(failed)s (lihat kolom galat).", ok=ok, failed=failed),
                'type': 'success' if not failed else 'warning',
                'sticky': bool(failed),
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    @api.model
    def _cron_kirim_ulang_mazta(self):
        """Kirim kabar yang menunggu, dan coba ulang yang gagal (cron, tiap 10 menit atau segera setelah MOU)."""
        for rec in self.search([('state', '=', 'mou'), ('mazta_callback_state', 'in', ('pending', 'failed')),
                                ('finance_request_id', '!=', False)], limit=50):
            rec._mazta_kirim_callback()
