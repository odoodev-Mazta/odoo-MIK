from odoo import models
from odoo.exceptions import ValidationError

class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    def button_start(self):
        res = super().button_start()

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

        res = super().button_finish()

        for wo in self:

            plan = wo.production_id.production_plan_id

            if plan:

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