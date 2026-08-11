from odoo import fields, models

class MrpProduction(models.Model):
    _inherit = "mrp.production"

    qc_schedule_ids = fields.One2many(
        "production.qc.schedule",
        "production_id",
        string="Quality Checks",
    )