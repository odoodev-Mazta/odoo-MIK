from odoo import Command, api, fields, models


class ProductionQcLog(models.Model):
    """Laporan QC: satu baris tiap kali QC menyatakan Lulus / Gagal. Tidak ikut terhapus saat tahap diulang."""

    _name = "mrp.production.qc.log"
    _description = "Laporan QC Tahap Produksi"
    _order = "qc_date desc, id desc"

    plan_stage_id = fields.Many2one("mrp.production.plan.stage", string="Tahap Proses", ondelete="set null", index=True)
    plan_id = fields.Many2one("mrp.production.plan", string="Plan Produksi", index=True)
    production_id = fields.Many2one("mrp.production", string="Perintah Produksi")
    product_id = fields.Many2one("product.product", string="Produk")
    stage_id = fields.Many2one("mrp.production.stage", string="Tahap")
    batch_no = fields.Char(string="No. Batch")
    attempt = fields.Integer(string="Percobaan ke-")
    qty_good = fields.Float(string="Qty Bagus")
    qty_reject = fields.Float(string="Qty Reject")
    started_by_id = fields.Many2one("res.users", string="Dikerjakan Oleh")
    submitted_by_id = fields.Many2one("res.users", string="Diajukan Oleh")
    submit_date = fields.Datetime(string="Tgl Diajukan")
    qc_user_id = fields.Many2one("res.users", string="Diperiksa Oleh (QC)")
    qc_date = fields.Datetime(string="Tgl Diperiksa")
    result = fields.Selection([("passed", "Lulus"), ("failed", "Gagal")], string="Hasil")
    reason = fields.Text(string="Catatan / Alasan Gagal")
    failed_parameters = fields.Char(string="Parameter Gagal")
    line_ids = fields.One2many("mrp.production.qc.log.line", "log_id", string="Hasil Parameter")

    @api.depends("stage_id", "product_id", "attempt", "result")
    def _compute_display_name(self):
        labels = dict(self._fields["result"].selection)
        for log in self:
            log.display_name = f"QC {log.stage_id.name or ''} - {log.product_id.display_name or ''} (#{log.attempt}, {labels.get(log.result, '')})"


class ProductionQcLogLine(models.Model):
    _name = "mrp.production.qc.log.line"
    _description = "Hasil Parameter Laporan QC"
    _order = "log_id, sequence, id"

    log_id = fields.Many2one("mrp.production.qc.log", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Parameter")
    specification = fields.Char(string="Spesifikasi")
    unit = fields.Char(string="Satuan")
    min_value = fields.Float(string="Minimum")
    max_value = fields.Float(string="Maksimum")
    actual = fields.Char(string="Nilai Aktual")
    result = fields.Selection(
        [("pending", "Belum Diisi"), ("passed", "Lulus"), ("failed", "Gagal")], string="Hasil",
    )


class ProductionPlanStageCheck(models.Model):
    """Batas di Perintah Produksi boleh diubah; ini salinan, jadi QC Template / QC Parameter tidak ikut berubah."""

    _inherit = "mrp.production.plan.stage.check"

    parameter_type = fields.Selection(default="number")

    def write(self, vals):
        tracked = {"min_value": "Minimum", "max_value": "Maksimum", "specification": "Spesifikasi"}
        changes = []
        if any(key in vals for key in tracked):
            for check in self:
                diffs = [
                    f"{label} {check[key] or '-'} → {vals[key] or '-'}"
                    for key, label in tracked.items() if key in vals and (check[key] or False) != (vals[key] or False)
                ]
                if diffs:
                    changes.append((check.stage_id, f"{check.name}: " + ", ".join(diffs)))
        result = super().write(vals)
        for stage, text in changes:
            stage.plan_id.message_post(
                body=f"Batas QC {stage._label()} diubah oleh {self.env.user.name} (khusus produksi ini): {text}",
                subtype_xmlid="mail.mt_note",
            )
        return result


class ProductionPlanStage(models.Model):
    _inherit = "mrp.production.plan.stage"

    qc_log_ids = fields.One2many("mrp.production.qc.log", "plan_stage_id", string="Laporan QC")

    def _create_qc_log(self, result):
        yesno = {"yes": "Ya", "no": "Tidak"}
        for stage in self:
            failed = stage.check_ids.filtered(lambda c: c.result == "failed")
            self.env["mrp.production.qc.log"].sudo().create({
                "plan_stage_id": stage.id,
                "plan_id": stage.plan_id.id,
                "production_id": stage.production_id.id,
                "product_id": stage.product_id.id,
                "stage_id": stage.stage_id.id,
                "batch_no": stage.batch_no,
                "attempt": stage.qc_attempt,
                "qty_good": stage.qty_good,
                "qty_reject": stage.qty_reject,
                "started_by_id": stage.started_by_id.id,
                "submitted_by_id": stage.submitted_by_id.id,
                "submit_date": stage.qc_submit_date,
                "qc_user_id": self.env.user.id,
                "qc_date": fields.Datetime.now(),
                "result": result,
                "reason": stage.qc_note,
                "failed_parameters": ", ".join(failed.mapped("name")) or False,
                "line_ids": [Command.create({
                    "sequence": check.sequence,
                    "name": check.name,
                    "specification": check.specification,
                    "unit": check.unit,
                    "min_value": check.min_value,
                    "max_value": check.max_value,
                    "actual": yesno.get(check.actual_yesno) if check.parameter_type == "boolean" else check.actual_value,
                    "result": check.result,
                }) for check in stage.check_ids],
            })

    def action_qc_pass(self):
        # Yang lulus dicatat di sini; yang gagal karena parameter dicatat di action_qc_fail.
        result = super().action_qc_pass()
        self.filtered(lambda s: s.state == "done" and s.qc_state == "passed" and not s.qc_log_ids.filtered(
            lambda log: log.result == "passed" and log.attempt == s.qc_attempt
        ))._create_qc_log("passed")
        return result

    def action_qc_fail(self):
        # Dicatat sebelum tahap direset (parameter & catatan masih ada).
        self._check_qc_access()
        if self._need_fail_reason():
            return super().action_qc_fail()  # popup alasan; dicatat setelah alasan diisi
        for stage in self:
            if stage.state == "waiting_qc" and stage.qc_note:
                stage._create_qc_log("failed")
        return super().action_qc_fail()
