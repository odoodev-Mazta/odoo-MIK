from odoo import models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

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
            "context": {"default_sale_order_id": self.id},
        }
