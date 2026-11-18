from odoo import fields, models


class ProductionPlanStageFailWizard(models.TransientModel):
    _name = "mrp.production.plan.stage.fail.wizard"
    _description = "Alasan QC Gagal"

    stage_ids = fields.Many2many(
        "mrp.production.plan.stage", "mrp_stage_fail_wizard_rel", "wizard_id", "stage_id", string="Tahap",
    )
    reason = fields.Char(string="Alasan Gagal", required=True)

    def action_confirm(self):
        self.ensure_one()
        stages = self.stage_ids.filtered(lambda s: s.state == "waiting_qc")
        stages.write({"qc_note": self.reason})
        stages.action_qc_fail()
        return {"type": "ir.actions.act_window_close"}
