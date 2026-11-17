from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    production_plan_ids = fields.Many2many(
        "mrp.production.plan",
        string="Plan Production",
        compute="_compute_production_plan_ids",
        help="Plan Production dari Sales Order pengiriman ini.",
    )

    def _compute_production_plan_ids(self):
        Plan = self.env["mrp.production.plan"]
        for picking in self:
            picking.production_plan_ids = (
                Plan.search([("sale_order_id", "=", picking.sale_id.id)]) if picking.sale_id else Plan
            )
