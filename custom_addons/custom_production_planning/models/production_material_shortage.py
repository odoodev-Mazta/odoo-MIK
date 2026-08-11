from odoo import models,fields

class ProductionMaterialShortage(models.Model):
    _name = "mrp.production.material.shortage"
    _description = "Production Material Shortage"

    plan_id = fields.Many2one(
        "mrp.production.plan",
        required=True,
        ondelete="cascade"
    )

    product_id = fields.Many2one(
        "product.product",
        string="Material"
    )

    required_qty = fields.Float(
        string="Required Quantity",
    )

    available_qty = fields.Float(
        string="Available Quantity",
    )

    shortage_qty = fields.Float(
        string="Shortage Quantity",
    )