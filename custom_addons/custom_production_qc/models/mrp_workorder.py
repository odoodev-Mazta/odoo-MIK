from odoo import models, fields, api
from odoo.exceptions import ValidationError


class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"


    qc_schedule_ids = fields.One2many(
        "production.qc.schedule",
        "workorder_id",
        string="Quality Checks",
    )


    qc_schedule_count = fields.Integer(
        string="QC Count",
        compute="_compute_qc_count"
    )


    def _compute_qc_count(self):
        for wo in self:
            wo.qc_schedule_count = len(
                wo.qc_schedule_ids
            )

    @api.model_create_multi
    def create(self, vals_list):

        records = super().create(vals_list)

        records.action_generate_qc()

        return records

    def action_generate_qc(self):

        QC = self.env["production.qc.schedule"]
        Template = self.env["production.qc.template"]

        for wo in self:

            existing = QC.search([
                ("workorder_id", "=", wo.id)
            ], limit=1)

            if existing:
                continue

            template = Template.search([
                ("operation_id", "=", wo.operation_id.id)
            ], limit=1)

            # Jika operation tidak punya QC Template,
            # maka Work Order ini tidak membutuhkan QC
            if not template:
                continue

            qc = QC.create({
                "name": f"QC - {wo.name}",
                "workorder_id": wo.id,
                "production_id": wo.production_id.id,
                "qc_template_id": template.id,
                "state": "waiting",
            })

            qc.action_generate_checklist()

        return True

    def action_open_qc_schedule(self):

        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Quality Checks",
            "res_model": "production.qc.schedule",
            "view_mode": "list,form",
            "domain": [
                ("workorder_id", "=", self.id)
            ],
            "context": {
                "default_workorder_id": self.id,
                "default_production_id": self.production_id.id,
            }
        }

    def button_start(self):

        res = super().button_start()

        qc_schedules = self.env[
            "production.qc.schedule"
        ].search([
            ("workorder_id", "in", self.ids)
        ])

        for qc in qc_schedules:

            if qc.state == "waiting":
                qc.state = "progress"

        return res

    def button_finish(self):
        for wo in self:

            qc_schedules = self.env[
                "production.qc.schedule"
            ].search([
                ("workorder_id", "=", wo.id)
            ])

            if qc_schedules:

                failed_qc = qc_schedules.filtered(
                    lambda qc: qc.state == "failed"
                )

                if failed_qc:
                    raise ValidationError(
                        f"Cannot finish {wo.name}. QC failed."
                    )

                unfinished_qc = qc_schedules.filtered(
                    lambda qc: qc.state != "done"
                )

                if unfinished_qc:
                    raise ValidationError(
                        f"Please complete QC first for {wo.name}."
                    )

        return super().button_finish()