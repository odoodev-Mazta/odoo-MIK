import math
from datetime import datetime, timedelta

from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, ValidationError


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
    workcenter_id = fields.Many2one(
        "mrp.workcenter",
        string="Work Center",
        help="Work Center bawaan untuk Work Order tahap ini. "
             "Bila mesin yang dipilih punya Work Center sendiri, itu yang dipakai.",
    )
    active = fields.Boolean(default=True)

    @api.model
    def _link_default_workcenters(self):
        """Isi Work Center bawaan tiap tahap dari data (hanya yang masih kosong)."""
        mapping = {
            "stage_penimbangan": "wc_penimbangan",
            "stage_mixing": "wc_mixing",
            "stage_filling": "wc_filling",
            "stage_labeling": "wc_labeling",
            "stage_coding": "wc_coding",
            "stage_packing": "wc_packing",
        }
        for stage_xmlid, wc_xmlid in mapping.items():
            stage = self.env.ref(f"custom_production_planning.{stage_xmlid}", raise_if_not_found=False)
            workcenter = self.env.ref(f"custom_production_planning.{wc_xmlid}", raise_if_not_found=False)
            if workcenter and workcenter.company_id:
                # Dipakai semua perusahaan; kalau terkunci di satu perusahaan, Work Center
                # tidak tampil bagi user yang sedang aktif di perusahaan lain.
                # Jam kerja juga harus tidak terikat perusahaan, kalau tidak Odoo menolak.
                calendar = self.env["resource.calendar"].sudo().search([("company_id", "=", False)], limit=1)
                if not calendar:
                    calendar = self.env["resource.calendar"].sudo().create({
                        "name": "Jam Kerja Standar (40 jam/minggu)",
                        "company_id": False,
                    })
                workcenter.write({"company_id": False, "resource_calendar_id": calendar.id})
            if stage and workcenter and not stage.workcenter_id:
                stage.workcenter_id = workcenter


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
    batch_label = fields.Char(string="Batch", compute="_compute_batch_label")

    @api.depends("plan_id.stage_ids.product_line_id", "product_line_id")
    def _compute_batch_label(self):
        for stage in self:
            lines = stage.plan_id.stage_ids.product_line_id.sorted("id")
            same = lines.filtered(lambda l: l.bom_product_id == stage.product_line_id.bom_product_id)
            if len(same) > 1 and stage.product_line_id in same:
                stage.batch_label = f"Batch {list(same.ids).index(stage.product_line_id.id) + 1}/{len(same)}"
            else:
                stage.batch_label = False

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
    machine_operator_count = fields.Integer(related="machine_id.operator_count", string="Pekerja")
    machine_capacity = fields.Float(
        string="Kapasitas/Hari", compute="_compute_machine_capacity",
        help="Kapasitas terbesar mesin ini per hari.",
    )

    @api.depends("machine_id.capacity_ids.capacity_per_day")
    def _compute_machine_capacity(self):
        for stage in self:
            caps = stage.machine_id.capacity_ids.mapped("capacity_per_day")
            stage.machine_capacity = max(caps) if caps else 0.0

    state = fields.Selection(
        [
            ("todo", "Belum Mulai"),
            ("in_progress", "Berjalan"),
            ("waiting_qc", "Menunggu QC"),
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
    qc_submit_date = fields.Datetime(string="Diajukan QC", readonly=True, copy=False)

    capacity_id = fields.Many2one(
        "mrp.production.machine.capacity",
        string="Kapasitas",
        domain="[('machine_id', '=', machine_id)]",
        help="Pilih jenis dan ukuran kemasan yang dikerjakan mesin ini, mis. Tube 20 gr.",
    )
    capacity_per_day = fields.Float(related="capacity_id.capacity_per_day", string="Kapasitas/Hari")
    capacity_uom = fields.Many2one(related="capacity_id.uom_id", string="Satuan")
    capacity_qty = fields.Float(
        string="Qty Dihitung",
        help="Qty yang dibagi kapasitas. Isi sesuai satuan kapasitas (mis. kg untuk Mixing).",
    )
    days_needed = fields.Integer(string="Hari Dibutuhkan", compute="_compute_capacity_check")
    days_available = fields.Integer(string="Hari Tersedia", compute="_compute_capacity_check")
    capacity_warning = fields.Boolean(string="Kapasitas Kurang", compute="_compute_capacity_check")

    @api.depends("capacity_id.capacity_per_day", "capacity_qty", "date_start", "date_end")
    def _compute_capacity_check(self):
        for stage in self:
            needed = available = 0
            if stage.capacity_per_day and stage.capacity_qty:
                needed = math.ceil(stage.capacity_qty / stage.capacity_per_day)
            if stage.date_start and stage.date_end:
                available = (stage.date_end - stage.date_start).days + 1
            stage.days_needed = needed
            stage.days_available = available
            stage.capacity_warning = bool(needed and available and needed > available)

    @api.onchange("machine_id")
    def _onchange_machine_id_capacity(self):
        for stage in self:
            capacities = stage.machine_id.capacity_ids
            if stage.capacity_id.machine_id != stage.machine_id:
                stage.capacity_id = capacities if len(capacities) == 1 else False

    @api.onchange("capacity_id")
    def _onchange_capacity_id_qty(self):
        for stage in self:
            if stage.capacity_id and not stage.capacity_qty:
                stage.capacity_qty = stage.qty_plan

    workorder_id = fields.Many2one("mrp.workorder", string="Work Order", copy=False, ondelete="set null")

    def _get_workcenter(self):
        self.ensure_one()
        return self.machine_id.workcenter_id or self.stage_id.workcenter_id

    def _ensure_workorder(self):
        """Buat Work Order untuk tahap ini di Perintah Produksi produknya (bila belum ada)."""
        for stage in self:
            order = stage.production_id
            if stage.workorder_id or not order or order.state in ("done", "cancel"):
                continue
            workcenter = stage._get_workcenter()
            if not workcenter:
                continue
            days = (stage.date_end - stage.date_start).days + 1 if stage.date_start and stage.date_end else 0
            name = stage.stage_id.name + (f" · {stage.batch_label}" if stage.batch_label else "")
            stage.workorder_id = self.env["mrp.workorder"].create({
                "name": name,
                "production_id": order.id,
                "workcenter_id": workcenter.id,
                "sequence": stage.sequence,
                "duration_expected": (days or 1) * 480.0,
            })

    def _sync_workorder(self, action):
        """Samakan status Work Order dengan tahap: start / pending / finish / reset."""
        for stage in self:
            workorder = stage.workorder_id
            if not workorder or workorder.state in ("done", "cancel"):
                continue
            if action == "start":
                workcenter = stage._get_workcenter()
                if workcenter and workorder.workcenter_id != workcenter and not workorder.leave_id:
                    workorder.workcenter_id = workcenter
                workorder.button_start()
            elif action == "pending":
                workorder.button_pending()
            elif action == "finish":
                workorder.qty_produced = stage.qty_good
                workorder.button_finish()
            elif action == "reset":
                workorder.button_pending()
                workorder.write({"state": "ready"})

    is_late = fields.Boolean(
        string="Terlambat", compute="_compute_is_late",
        help="Tanggal selesai rencana sudah lewat tetapi tahap belum selesai.",
    )

    @api.depends("date_end", "state")
    def _compute_is_late(self):
        today = fields.Date.context_today(self)
        for stage in self:
            stage.is_late = bool(stage.date_end and stage.date_end < today and stage.state != "done")

    def action_open_mo(self):
        self.ensure_one()
        if not self.production_id:
            raise ValidationError("Perintah Produksi untuk produk ini belum dibuat.")
        return {
            "type": "ir.actions.act_window",
            "name": self.production_id.name,
            "res_model": "mrp.production",
            "res_id": self.production_id.id,
            "views": [(False, "form")],
        }

    def _notify_qc_users(self):
        """Beri tugas (to-do) ke tiap petugas QC supaya tahap ini muncul di daftar aktivitas mereka."""
        self.ensure_one()
        qc_users = self.env.ref("custom_production_planning.group_production_qc").sudo().all_user_ids
        for user in qc_users:
            self.plan_id.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=user.id,
                summary=self._qc_activity_summary(),
                note=f"Qty bagus {self.qty_good:g}. Buka menu Produksi > Antrean QC untuk memeriksa.",
                date_deadline=fields.Date.context_today(self),
            )

    def _qc_activity_summary(self):
        self.ensure_one()
        return f"QC: {self._label()}"

    def _close_qc_activities(self):
        for stage in self:
            summary = stage._qc_activity_summary()
            stage.plan_id.activity_ids.filtered(lambda act: act.summary == summary).sudo().action_feedback(
                feedback="Pemeriksaan QC selesai."
            )

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
        today = fields.Date.context_today(self)
        early = self.filtered(lambda s: s.date_start and s.date_start > today and s.state == "todo")
        result = self._start_stages()
        if early:
            labels = ", ".join(early.mapped(lambda s: s._label()))
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Dimulai lebih awal dari jadwal",
                    "message": f"{labels} dijadwalkan mulai {min(early.mapped('date_start'))}. "
                               "Tahap tetap dijalankan, jadwal hanya rencana.",
                    "type": "warning",
                    "sticky": False,
                    "next": {"type": "ir.actions.client", "tag": "reload"},
                },
            }
        return result

    def _start_stages(self):
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
            stage._ensure_workorder()
            stage._sync_workorder("start")
        return True

    def _check_qc_access(self):
        """Hanya petugas QC (atau Administrator) yang boleh menyatakan lulus / gagal."""
        user = self.env.user
        if not (user.has_group("custom_production_planning.group_production_qc") or user.has_group("base.group_system")):
            raise AccessError("Hanya petugas QC yang boleh menyatakan QC lulus atau gagal.")

    def _check_batch_fields(self):
        self.ensure_one()
        if self.set_batch:
            if not self.batch_no or not self.expiry_date:
                raise ValidationError(f"Isi No. Batch dan Tanggal Expired tahap {self._label()} sebelum diajukan QC.")
            if self.expiry_date <= fields.Date.context_today(self):
                raise ValidationError(f"Tanggal Expired tahap {self._label()} harus setelah hari ini.")

    def _check_qty_limit(self):
        self.ensure_one()
        previous = self._previous()
        limit = previous.qty_good if previous else self.qty_plan
        if limit and self.qty_good > limit:
            raise ValidationError(
                f"Tahap {self._label()}: Qty Bagus ({self.qty_good:g}) melebihi "
                f"{'hasil tahap sebelumnya' if previous else 'qty rencana'} ({limit:g})."
            )

    def action_submit_qc(self):
        """Operator menyatakan tahap selesai dikerjakan; QC yang memeriksa."""
        for stage in self:
            if stage.state != "in_progress":
                raise ValidationError(f"Tahap {stage._label()} belum berjalan.")
            if stage.qty_good <= 0:
                raise ValidationError(f"Isi Qty Bagus tahap {stage._label()} sebelum diajukan QC.")
            stage._check_batch_fields()
            stage._check_qty_limit()
            stage.write({
                "state": "waiting_qc",
                "qc_state": "pending",
                "qc_submit_date": fields.Datetime.now(),
            })
            qc_users = self.env.ref("custom_production_planning.group_production_qc").sudo().all_user_ids
            stage.plan_id.message_post(
                body=f"Tahap {stage._label()} diajukan ke QC ({stage.qty_good:g} bagus). Menunggu pemeriksaan.",
                subtype_xmlid="mail.mt_note",
                partner_ids=qc_users.partner_id.ids,
            )
            stage._sync_workorder("pending")
            stage._notify_qc_users()
        return True

    def action_qc_pass(self):
        self._check_qc_access()
        for stage in self:
            if stage.state != "waiting_qc":
                raise ValidationError(f"Tahap {stage._label()} belum diajukan ke QC.")
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
            stage._check_qty_limit()
            stage.write({
                "qc_state": "passed",
                "qc_user_id": self.env.user.id,
                "qc_date": fields.Datetime.now(),
                "state": "done",
                "date_end_actual": fields.Datetime.now(),
            })
            stage._sync_workorder("finish")
            stage._close_qc_activities()
            following = stage._siblings().filtered(lambda s: s.sequence > stage.sequence or (s.sequence == stage.sequence and s.id > stage.id))[:1]
            partners = (stage.user_id | following.user_id).partner_id.ids
            stage.plan_id.message_post(
                body=f"QC lulus: {stage._label()}."
                     + (f" Tahap berikutnya: {following._label()}." if following else " Semua tahap produk ini selesai."),
                subtype_xmlid="mail.mt_note",
                partner_ids=partners,
            )
            if stage.product_line_id and stage == stage._siblings()[-1]:
                stage.plan_id._finish_product_line(stage.product_line_id, stage.qty_good)
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
        self._check_qc_access()
        for stage in self:
            if stage.state != "waiting_qc":
                raise ValidationError(f"Tahap {stage._label()} belum diajukan ke QC.")
            if not stage.qc_note:
                raise ValidationError(f"Isi Catatan QC tahap {stage._label()} sebelum menyatakan gagal.")
            stage.plan_id.message_post(
                body=f"QC gagal di tahap {stage._label()}: {stage.qc_note}. Tahap diulang.",
                subtype_xmlid="mail.mt_note",
                partner_ids=stage.user_id.partner_id.ids,
            )
            stage._close_qc_activities()
            stage.write({
                "state": "todo",
                "qc_state": "failed",
                "qc_user_id": self.env.user.id,
                "qc_date": fields.Datetime.now(),
                "attempts": stage.attempts + 1,
                "date_start_actual": False,
                "qc_submit_date": False,
            })
            stage._sync_workorder("reset")
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
