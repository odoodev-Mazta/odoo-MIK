import logging

from odoo import api, fields, models
from odoo.tools.sql import table_exists

_logger = logging.getLogger(__name__)

# (model, method, keterangan). Dipasang saat registry dimuat; model/method yang tidak ada dilewati.
LOGGED_ACTIONS = [
    ("usulan.usulan.dana", "action_approve_head", "Disetujui Head Dept"),
    ("usulan.usulan.dana", "action_approve_coo", "Disetujui COO"),
    ("usulan.usulan.dana", "action_approve_ceo", "Disetujui CEO"),
    ("usulan.usulan.dana", "action_approve_finance", "Disetujui Finance"),
    ("usulan.usulan.dana", "action_reject", "Ditolak"),
    ("usulan.usulan.dana", "action_reject_tax", "Ditolak (cek pajak)"),
    ("usulan.up.country", "action_approve_head", "Disetujui Head Dept"),
    ("usulan.up.country", "action_approve_purchasing", "Disetujui Purchasing"),
    ("usulan.up.country", "action_reject", "Ditolak"),
    ("usulan.dana.tax", "action_validate", "Cek pajak divalidasi"),
    ("purchase.request", "action_approve", "Disetujui"),
    ("purchase.request", "action_reject", "Ditolak"),
    ("purchase.order", "button_approve", "PO disetujui"),
    ("registrasi.produk", "action_approve_marketing", "Disetujui Marketing"),
    ("registrasi.produk", "action_approve_regulatory", "Disetujui Regulatory"),
    ("registrasi.produk", "action_approve_factory", "Disetujui Factory Manager"),
    ("registrasi.produk", "action_finance_approve_payment", "Pembayaran disetujui Finance"),
    ("registrasi.brand", "action_approve", "Disetujui"),
    ("registrasi.brand", "action_reject_to_resubmit", "Dikembalikan untuk diajukan ulang"),
    ("registrasi.brand", "action_mark_rejected", "Ditolak"),
    ("design.approval", "action_approve_marketing", "Disetujui Marketing"),
    ("design.approval", "action_approve_client", "Disetujui Klien"),
    ("design.approval", "action_approve_ro", "Disetujui RO"),
    ("design.approval", "action_upload_done", "Design final diunggah"),
    ("design.approval", "action_reject", "Ditolak"),
    ("mrp.production.plan", "action_approve", "Plan Produksi disetujui"),
    ("mrp.production.plan.stage", "action_qc_pass", "QC lulus"),
    ("mrp.production.plan.stage", "action_qc_fail", "QC gagal"),
]


class ApprovalLog(models.Model):
    """Catatan siapa menyetujui / menolak apa dan kapan. Hanya bisa dibaca, tidak bisa diubah."""
    _name = "approval.log"
    _description = "Riwayat Approval"
    _order = "date desc, id desc"

    date = fields.Datetime(string="Waktu", default=fields.Datetime.now, readonly=True, index=True)
    user_id = fields.Many2one("res.users", string="Oleh", readonly=True, index=True)
    action = fields.Char(string="Tindakan", readonly=True)
    model_label = fields.Char(string="Jenis Dokumen", readonly=True)
    res_model = fields.Char(string="Model", readonly=True, index=True)
    res_id = fields.Integer(string="ID Dokumen", readonly=True)
    record_name = fields.Char(string="Dokumen", readonly=True)
    state_before = fields.Char(string="Status Sebelum", readonly=True)
    state_after = fields.Char(string="Status Sesudah", readonly=True)

    def init(self):
        # Registry bisa dimuat dengan kode baru sebelum modul di-upgrade (mis. saat build). Buat tabelnya bila belum
        # ada supaya tidak muncul ERROR "Model approval.log has no table" di log.
        if not table_exists(self.env.cr, self._table):
            self._auto_init()

    def action_open_record(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": self.res_model,
            "res_id": self.res_id,
            "view_mode": "form",
            "target": "current",
        }

    @api.model
    def _log(self, records, action, before):
        if not table_exists(self.env.cr, self._table):
            return
        vals_list = []
        for record in records.exists():
            old = before.get(record.id)
            new = record.state if "state" in record._fields else None
            if "state" in record._fields and old == new:
                continue  # tombol ditekan tapi status tidak berubah (mis. hanya membuka wizard)
            vals_list.append({
                "user_id": self.env.uid,
                "action": action,
                "model_label": record._description,
                "res_model": record._name,
                "res_id": record.id,
                "record_name": record.display_name,
                "state_before": old,
                "state_after": new,
            })
        if vals_list:
            with self.env.cr.savepoint():
                self.sudo().create(vals_list)

    @api.model
    def _register_hook(self):
        super()._register_hook()
        for model_name, method, label in LOGGED_ACTIONS:
            if model_name not in self.env.registry:
                continue
            cls = self.env.registry[model_name]
            original = getattr(cls, method, None)
            if original is None or getattr(original, "_approval_logged", False):
                continue
            setattr(cls, method, self._make_logged(original, label))

    @staticmethod
    def _make_logged(original, label):
        def logged(self, *args, **kwargs):
            before = {}
            if "state" in self._fields:
                before = {record.id: record.state for record in self}
            result = original(self, *args, **kwargs)
            try:
                self.env["approval.log"]._log(self, label, before)
            except Exception:  # pencatatan tidak boleh menggagalkan approval
                _logger.exception("Gagal mencatat riwayat approval %s", label)
            return result

        logged._approval_logged = True
        logged.__name__ = original.__name__
        logged.__doc__ = original.__doc__
        return logged
