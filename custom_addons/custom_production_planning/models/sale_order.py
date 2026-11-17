from odoo import api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    production_plan_ids = fields.One2many("mrp.production.plan", "sale_order_id", string="Plan Production")
    production_plan_count = fields.Integer(string="Jumlah Plan Production", compute="_compute_production_plan_count")

    @api.depends("production_plan_ids")
    def _compute_production_plan_count(self):
        for order in self:
            order.production_plan_count = len(order.production_plan_ids)

    def action_view_production_plans(self):
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": f"Plan Production {self.name}",
            "res_model": "mrp.production.plan",
            "domain": [("sale_order_id", "=", self.id)],
            "views": [(False, "list"), (False, "form")],
        }
        if len(self.production_plan_ids) == 1:
            action.update(res_id=self.production_plan_ids.id, views=[(False, "form")])
        return action

    def action_send_to_plan_production(self):
        """Buka form Plan Production baru yang terisi dari SO ini (hanya SO berstatus Sales Order)."""
        self.ensure_one()
        if self.state != "sale":
            raise UserError("Hanya Sales Order yang sudah dikonfirmasi yang bisa dikirim ke Plan Production.")
        return {
            "type": "ir.actions.act_window",
            "name": "Plan Production",
            "res_model": "mrp.production.plan",
            "view_mode": "form",
            "target": "current",
            "context": {"default_sale_order_id": self.id, "from_sale_order_button": True},
        }
