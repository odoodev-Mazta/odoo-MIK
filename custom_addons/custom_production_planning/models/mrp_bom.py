from odoo import fields, models


class MrpBomLine(models.Model):
    _inherit = "mrp.bom.line"

    production_stage_id = fields.Many2one(
        "mrp.production.stage",
        string="Dipakai di Tahap",
        help="Tahap produksi yang memakai bahan ini (mis. stiker di Labeling). "
             "Kosong = dipakai sejak tahap pertama.",
    )
