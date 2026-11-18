from odoo import api, fields, models

STAGE_TO_SCHEDULE = {
    "waiting_qc": "waiting",
    "done": "done",
}


class QCSchedule(models.Model):
    _inherit = "production.qc.schedule"

    # Tahap tanpa Work Center tidak punya Work Order; QC Schedule tetap dibuat.
    workorder_id = fields.Many2one(required=False)
    plan_stage_id = fields.Many2one(
        "mrp.production.plan.stage", string="Tahap Proses", index=True, ondelete="cascade",
        help="Tahap di Plan Produksi yang diajukan ke QC. Pemeriksaan & approve dilakukan di tahap ini.",
    )
    plan_id = fields.Many2one(related="plan_stage_id.plan_id", string="Plan Produksi", store=True)
    stage_name_id = fields.Many2one(related="plan_stage_id.stage_id", string="Tahap", store=True)
    submitted_by_id = fields.Many2one(related="plan_stage_id.submitted_by_id", string="Diajukan Oleh")
    qc_user_id = fields.Many2one(related="plan_stage_id.qc_user_id", string="Approve QC")
    stage_qty_good = fields.Float(related="plan_stage_id.qty_good", string="Qty Bagus")

    def action_open_stage_check(self):
        """Buka form pemeriksaan tahap (parameter QC, Lulus / Gagal)."""
        self.ensure_one()
        return self.plan_stage_id.action_open_checks()

    def action_done(self):
        stage_linked = self.filtered("plan_stage_id")
        for rec in stage_linked:
            rec.plan_stage_id.action_qc_pass()
        return super(QCSchedule, self - stage_linked).action_done() if self - stage_linked else True

    def action_failed(self):
        stage_linked = self.filtered("plan_stage_id")
        for rec in stage_linked:
            rec.plan_stage_id.action_qc_fail()
        return super(QCSchedule, self - stage_linked).action_failed() if self - stage_linked else True


class ProductionPlanStage(models.Model):
    _inherit = "mrp.production.plan.stage"

    qc_schedule_ids = fields.One2many("production.qc.schedule", "plan_stage_id", string="QC Schedule")

    def _sync_qc_schedule(self):
        """Ajukan QC -> muncul di QC Schedule (dibuat sekali, dipakai ulang bila diajukan lagi)."""
        Schedule = self.env["production.qc.schedule"].sudo()
        for stage in self:
            schedule = stage.sudo().qc_schedule_ids[:1]
            if stage.state == "waiting_qc":
                vals = {
                    "name": f"QC - {stage._label()}" + (f" · {stage.batch_label}" if stage.batch_label else ""),
                    "plan_stage_id": stage.id,
                    "production_id": stage.production_id.id,
                    "workorder_id": stage.workorder_id.id,
                    "state": "waiting",
                    "inspection_date": False,
                }
                if not stage.production_id:
                    continue
                if schedule:
                    schedule.write(vals)
                else:
                    Schedule.create(vals)
            elif schedule:
                if stage.state == "done":
                    schedule.write({"state": "done", "inspection_date": stage.qc_date})
                elif stage.qc_state == "failed":
                    schedule.write({"state": "failed", "inspection_date": stage.qc_date})

    def action_submit_qc(self):
        result = super().action_submit_qc()
        self._sync_qc_schedule()
        return result

    def action_qc_pass(self):
        result = super().action_qc_pass()
        self._sync_qc_schedule()
        return result

    def action_qc_fail(self):
        result = super().action_qc_fail()
        self._sync_qc_schedule()
        return result

    @api.model
    def _backfill_qc_schedule(self):
        """Tahap yang sudah terlanjur diajukan QC (sebelum fitur ini) ikut muncul di QC Schedule."""
        self.search([("state", "=", "waiting_qc"), ("qc_schedule_ids", "=", False)])._sync_qc_schedule()
