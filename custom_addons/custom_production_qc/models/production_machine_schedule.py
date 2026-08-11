from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ProductionMachineSchedule(models.Model):
    _inherit = "mrp.production.machine.schedule"

    # @api.model_create_multi
    # def create(self, vals_list):
    #     records = super().create(vals_list)
    #
    #     qc_vals = []
    #
    #     for record in records:
    #
    #         machine = record.machine_id
    #
    #         # cek apakah machine ini butuh QC
    #         if not machine.need_qc:
    #             continue
    #
    #         # machine butuh QC tapi belum punya template
    #         if not machine.qc_template_id:
    #             raise ValidationError(
    #                 f"QC Template belum diatur untuk machine {machine.name}"
    #             )
    #
    #         qc_vals.append({
    #             "machine_schedule_id": record.id,
    #             "qc_template_id": machine.qc_template_id.id,
    #             "state": "waiting",
    #         })
    #
    #     if qc_vals:
    #         self.env["production.qc.schedule"].create(qc_vals)
    #
    #     return records