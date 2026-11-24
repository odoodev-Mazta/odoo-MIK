from odoo import _, models
from odoo.exceptions import UserError, ValidationError

class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    def _check_run_from_stage(self):
        """Work Order milik tahap Proses Produksi hanya boleh dijalankan dari tahapnya."""
        if self.env.context.get("from_production_stage"):
            return
        if self.env["mrp.production.plan.stage"].sudo().search_count(
            [("workorder_id", "in", self.ids)]
        ):
            raise UserError(_(
                "Work Order ini dijalankan dari tab Proses Produksi (Mulai, Ajukan QC, QC Lulus). "
                "Tombol di Work Order tidak dipakai supaya statusnya selalu sama dengan tahap."
            ))

    def button_pending(self, *args, **kwargs):
        self._check_run_from_stage()
        return super().button_pending(*args, **kwargs)

    def button_start(self, *args, **kwargs):
        self._check_run_from_stage()
        res = super().button_start(*args, **kwargs)

        schedules = self.env[
            "mrp.production.machine.schedule"
        ].search([
            ("workorder_id", "in", self.ids)
        ])

        schedules.write({
            "state": "running"
        })

        return res

    def button_finish(self):

        self._check_run_from_stage()
        res = super().button_finish()

        for wo in self:

            plan = wo.production_id.production_plan_id

            # Plan berbasis tahap proses: status Done ditentukan oleh tahap & QC, bukan Work Order.
            if plan and not plan.stage_ids:

                workorders = plan.manufacturing_order_ids.mapped(
                    "workorder_ids"
                )

                if all(
                    w.state == "done"
                    for w in workorders
                ):
                    plan.state = "done"

        return res

    def action_cancel(self):
        res = super().action_cancel()

        schedules = self.env[
            "mrp.production.machine.schedule"
        ].search([
            ("workorder_id", "in", self.ids)
        ])

        schedules.write({
            "state": "planned"
        })

        return res