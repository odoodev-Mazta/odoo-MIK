from datetime import datetime, timedelta

from odoo import Command, api, fields, models
from odoo.exceptions import ValidationError


class ProductionStage(models.Model):
    _name = "mrp.production.stage"
    _description = "Tahap Proses Produksi"
    _order = "sequence, id"

    name = fields.Char(string="Tahap", required=True)
    sequence = fields.Integer(default=10)
    origin_type = fields.Selection(
        [
            ("both", "Lokal & Import"),
            ("lokal", "Lokal saja"),
            ("import", "Import saja"),
        ],
        string="Dipakai untuk",
        default="both",
        required=True,
    )
    set_batch = fields.Boolean(
        string="Tentukan Batch & Expired",
        help="Tahap ini menentukan nomor batch dan tanggal kedaluwarsa (Coding).",
    )
    parameter_ids = fields.One2many("mrp.production.stage.parameter", "stage_id", string="Parameter QC")
    active = fields.Boolean(default=True)


class ProductionPlanStage(models.Model):
    _name = "mrp.production.plan.stage"
    _description = "Jadwal Proses Production Plan"
    _order = "plan_id, product_line_id, sequence, id"

    plan_id = fields.Many2one(
        "mrp.production.plan",
        string="Production Plan",
        required=True,
        ondelete="cascade",
    )
    product_line_id = fields.Many2one(
        "mrp.production.plan.product.line",
        string="Baris Produk",
        ondelete="cascade",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Produk",
        related="product_line_id.bom_product_id",
    )
    qty_plan = fields.Float(
        string="Qty Rencana",
        related="product_line_id.production_qty",
    )
    production_id = fields.Many2one(
        "mrp.production",
        string="Perintah Produksi",
        compute="_compute_production_id",
        store=True,
    )
    sequence = fields.Integer(default=10)
    stage_id = fields.Many2one(
        "mrp.production.stage",
        string="Tahap",
        required=True,
    )
    date_start = fields.Date(string="Mulai")
    date_end = fields.Date(string="Selesai")
    user_id = fields.Many2one("res.users", string="PIC")
    machine_id = fields.Many2one(
        "mrp.production.machine",
        string="Mesin",
        help="Kosongkan bila tahap ini dikerjakan manual.",
    )
    state = fields.Selection(
        [
            ("todo", "Belum Mulai"),
            ("in_progress", "Berjalan"),
            ("done", "Selesai"),
        ],
        string="Status",
        default="todo",
        required=True,
    )
    note = fields.Char(string="Catatan")

    qty_good = fields.Float(string="Qty Bagus")
    qty_reject = fields.Float(string="Qty Reject")
    date_start_actual = fields.Datetime(string="Mulai Aktual", readonly=True, copy=False)
    date_end_actual = fields.Datetime(string="Selesai Aktual", readonly=True, copy=False)
    attempts = fields.Integer(string="Diulang", readonly=True, copy=False)

    set_batch = fields.Boolean(related="stage_id.set_batch")
    batch_no = fields.Char(string="No. Batch")
    expiry_date = fields.Date(string="Tanggal Expired")

    check_ids = fields.One2many("mrp.production.plan.stage.check", "stage_id", string="Parameter QC")
    has_checks = fields.Boolean(compute="_compute_has_checks")

    qc_state = fields.Selection(
        [
            ("pending", "Belum QC"),
            ("passed", "Lulus"),
            ("failed", "Gagal"),
        ],
        string="QC",
        default="pending",
        required=True,
        copy=False,
    )
    qc_note = fields.Char(string="Catatan QC")
    qc_user_id = fields.Many2one("res.users", string="Petugas QC", readonly=True, copy=False)
    qc_date = fields.Datetime(string="Waktu QC", readonly=True, copy=False)

    @api.depends("product_line_id.manufacturing_order_ids")
    def _compute_production_id(self):
        for stage in self:
            stage.production_id = stage.product_line_id.manufacturing_order_ids[:1]

    @api.depends("check_ids")
    def _compute_has_checks(self):
        for stage in self:
            stage.has_checks = bool(stage.check_ids)

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for stage in self:
            if stage.date_start and stage.date_end and stage.date_end < stage.date_start:
                raise ValidationError(
                    f"Tahap {stage.stage_id.name}: tanggal selesai tidak boleh "
                    "lebih awal dari tanggal mulai."
                )

    def _label(self):
        self.ensure_one()
        product = self.product_id.display_name
        return f"{self.stage_id.name} ({product})" if product else self.stage_id.name

    def _siblings(self):
        """Tahap lain milik produk yang sama di plan ini, berurutan."""
        self.ensure_one()
        return self.plan_id.stage_ids.filtered(
            lambda stage: stage.product_line_id == self.product_line_id
        ).sorted(key=lambda stage: (stage.sequence, stage.id))

    def _previous(self):
        siblings = self._siblings()
        index = siblings.ids.index(self.id)
        return siblings[index - 1] if index else self.browse()

    def action_start(self):
        for stage in self:
            if stage.plan_id.state != "running":
                raise ValidationError("Buat Perintah Produksi dulu. Tahap baru bisa dikerjakan setelah plan berstatus Running.")
            if stage.state != "todo":
                raise ValidationError(f"Tahap {stage._label()} sudah berjalan.")
            previous = stage._previous()
            if previous and previous.state != "done":
                raise ValidationError(f"Selesaikan tahap {previous._label()} dulu.")
            stage.write({
                "state": "in_progress",
                "date_start_actual": fields.Datetime.now(),
                "qc_state": "pending",
                "qc_note": False,
            })
            stage.check_ids.unlink()
            stage.check_ids = [Command.create({
                "sequence": parameter.sequence,
                "name": parameter.name,
                "specification": parameter.specification,
                "parameter_type": parameter.parameter_type,
                "unit": parameter.unit,
                "min_value": parameter.min_value,
                "max_value": parameter.max_value,
                "required": parameter.required,
            }) for parameter in stage.stage_id.parameter_ids]
            product = stage.product_id
            if stage.set_batch and not stage.expiry_date and product.use_expiration_date and product.expiration_time:
                stage.expiry_date = fields.Date.context_today(stage) + timedelta(days=product.expiration_time)
        return True

    def action_qc_pass(self):
        for stage in self:
            if stage.state != "in_progress":
                raise ValidationError(f"Tahap {stage._label()} belum berjalan.")
            if stage.qty_good <= 0:
                raise ValidationError(f"Isi Qty Bagus tahap {stage._label()} sebelum QC.")
            if stage.check_ids:
                missing = stage.check_ids.filtered(lambda check: check.required and check.result == "pending")
                if missing:
                    raise ValidationError(
                        f"Isi parameter QC tahap {stage._label()}: {', '.join(missing.mapped('name'))}."
                    )
                failed = stage.check_ids.filtered(lambda check: check.result == "failed")
                if failed:
                    stage.qc_note = "Di luar batas: " + ", ".join(
                        f"{check.name} ({check.actual_value or check.actual_yesno})" for check in failed
                    )
                    stage.action_qc_fail()
                    continue
            if stage.set_batch:
                if not stage.batch_no or not stage.expiry_date:
                    raise ValidationError(f"Isi No. Batch dan Tanggal Expired tahap {stage._label()} sebelum QC.")
                if stage.expiry_date <= fields.Date.context_today(stage):
                    raise ValidationError(f"Tanggal Expired tahap {stage._label()} harus setelah hari ini.")
            stage.write({
                "qc_state": "passed",
                "qc_user_id": self.env.user.id,
                "qc_date": fields.Datetime.now(),
            })
        return True

    def action_open_checks(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"QC {self._label()}",
            "res_model": self._name,
            "res_id": self.id,
            "views": [(self.env.ref("custom_production_planning.view_production_plan_stage_form").id, "form")],
            "target": "new",
        }

    def action_qc_fail(self):
        for stage in self:
            if stage.state != "in_progress":
                raise ValidationError(f"Tahap {stage._label()} belum berjalan.")
            if not stage.qc_note:
                raise ValidationError(f"Isi Catatan QC tahap {stage._label()} sebelum menyatakan gagal.")
            stage.plan_id.message_post(
                body=f"QC gagal di tahap {stage._label()}: {stage.qc_note}. Tahap diulang.",
                subtype_xmlid="mail.mt_note",
            )
            stage.write({
                "state": "todo",
                "qc_state": "failed",
                "qc_user_id": self.env.user.id,
                "qc_date": fields.Datetime.now(),
                "attempts": stage.attempts + 1,
                "date_start_actual": False,
            })
        return True

    def action_done(self):
        for stage in self:
            if stage.state != "in_progress":
                raise ValidationError(f"Tahap {stage._label()} belum berjalan.")
            if stage.qc_state != "passed":
                raise ValidationError(f"Tahap {stage._label()} belum lulus QC.")
            previous = stage._previous()
            limit = previous.qty_good if previous else stage.qty_plan
            if limit and stage.qty_good > limit:
                raise ValidationError(
                    f"Tahap {stage._label()}: Qty Bagus ({stage.qty_good:g}) melebihi "
                    f"{'hasil tahap sebelumnya' if previous else 'qty rencana'} ({limit:g})."
                )
            stage.write({"state": "done", "date_end_actual": fields.Datetime.now()})
            if stage.product_line_id and stage == stage._siblings()[-1]:
                stage.plan_id._finish_product_line(stage.product_line_id, stage.qty_good)
        return True


class ProductionStageParameter(models.Model):
    _name = "mrp.production.stage.parameter"
    _description = "Parameter QC Tahap Proses"
    _order = "stage_id, sequence, id"

    stage_id = fields.Many2one("mrp.production.stage", string="Tahap", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Parameter", required=True)
    specification = fields.Char(string="Spesifikasi")
    parameter_type = fields.Selection(
        [
            ("number", "Angka"),
            ("boolean", "Ya / Tidak"),
            ("text", "Teks"),
        ],
        string="Jenis",
        default="number",
        required=True,
    )
    unit = fields.Char(string="Satuan")
    min_value = fields.Float(string="Minimum", help="Kosongkan (0) bila tidak ada batas bawah.")
    max_value = fields.Float(string="Maksimum", help="Kosongkan (0) bila tidak ada batas atas.")
    required = fields.Boolean(string="Wajib", default=True)


class ProductionPlanStageCheck(models.Model):
    _name = "mrp.production.plan.stage.check"
    _description = "Hasil Pemeriksaan QC per Tahap"
    _order = "stage_id, sequence, id"

    stage_id = fields.Many2one("mrp.production.plan.stage", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    # Disalin dari master saat tahap dimulai, supaya riwayat tidak berubah bila master diedit.
    name = fields.Char(string="Parameter", required=True)
    specification = fields.Char(string="Spesifikasi")
    parameter_type = fields.Selection(
        [("number", "Angka"), ("boolean", "Ya / Tidak"), ("text", "Teks")],
        string="Jenis",
        required=True,
    )
    unit = fields.Char(string="Satuan")
    min_value = fields.Float(string="Minimum")
    max_value = fields.Float(string="Maksimum")
    required = fields.Boolean(string="Wajib", default=True)

    actual_value = fields.Char(string="Nilai Aktual")
    actual_yesno = fields.Selection([("yes", "Ya"), ("no", "Tidak")], string="Ya / Tidak")
    result = fields.Selection(
        [("pending", "Belum Diisi"), ("passed", "Lulus"), ("failed", "Gagal")],
        string="Hasil",
        compute="_compute_result",
        store=True,
    )

    @api.depends("parameter_type", "actual_value", "actual_yesno", "min_value", "max_value")
    def _compute_result(self):
        for check in self:
            if check.parameter_type == "boolean":
                check.result = (
                    "pending" if not check.actual_yesno
                    else "passed" if check.actual_yesno == "yes" else "failed"
                )
                continue
            text = (check.actual_value or "").strip()
            if not text:
                check.result = "pending"
            elif check.parameter_type == "text":
                check.result = "passed"
            else:
                try:
                    value = float(text.replace(",", "."))
                except ValueError:
                    check.result = "failed"
                    continue
                below = bool(check.min_value) and value < check.min_value
                above = bool(check.max_value) and value > check.max_value
                check.result = "failed" if below or above else "passed"
