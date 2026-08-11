from odoo import models, fields

class ProductionMachine(models.Model):
    _inherit = "mrp.production.machine"

    need_qc = fields.Boolean(
        string="Need QC",
        default=False
    )

    qc_template_id = fields.Many2one(
        "production.qc.template",
        string="QC Template"
    )