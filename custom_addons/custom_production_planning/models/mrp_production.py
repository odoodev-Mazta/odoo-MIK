from odoo import api, fields, models

class MrpProduction(models.Model):
    _inherit = "mrp.production"

    production_plan_id = fields.Many2one(
        "mrp.production.plan",
        string="Production Plan",
        readonly=True,
    )

    plan_mou_id = fields.Many2one(
        related="production_plan_id.mou_id",
        string="No. MOU",
    )

    plan_brand_name = fields.Char(
        related="production_plan_id.brand_name",
        string="Nama Brand",
    )

    production_plan_line_id = fields.Many2one(
        "mrp.production.plan.line",
        string="Production Plan Line",
    )

    production_plan_product_line_id = fields.Many2one(
        "mrp.production.plan.product.line",
        string="Production Plan Product",
        ondelete="set null",
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

    stage_ids = fields.One2many(
        "mrp.production.plan.stage",
        "production_id",
        string="Proses Produksi",
    )

    plan_sibling_mo_ids = fields.Many2many(
        "mrp.production",
        compute="_compute_plan_sibling_mo_ids",
        string="Produk Lain di Plan",
    )

    @api.depends("production_plan_id.manufacturing_order_ids")
    def _compute_plan_sibling_mo_ids(self):
        for mo in self:
            mo.plan_sibling_mo_ids = mo.production_plan_id.manufacturing_order_ids - mo
