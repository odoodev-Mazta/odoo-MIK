from odoo import fields, models

class MrpProduction(models.Model):
    _inherit = "mrp.production"

    production_plan_id = fields.Many2one(
        "mrp.production.plan",
        string="Production Plan",
        readonly=True,
    )

    production_plan_line_id = fields.Many2one(
        "mrp.production.plan.line",
        string="Production Plan Line",
    )

    def action_open_production_plan(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Production Plan",
            "res_model": "mrp.production.plan",
            "view_mode": "form",
            "res_id": self.production_plan_id.id,
            "target": "current",
        }