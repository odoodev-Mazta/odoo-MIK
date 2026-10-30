from odoo import models,fields,api

class CustomerProfile(models.Model):
    _name = 'customer.profile'
    _description = 'Customer Profile'

    name = fields.Char(required=True)

    partner_id = fields.Many2one(
        "res.partner",
        required=True,
        ondelete="cascade",
    )

    customer_level = fields.Selection(
        [
            ("low", "Low"),
            ("middle", "Middle"),
            ("high", "High"),
        ],
        default="low",
    )

    recommendation_line_ids = fields.One2many(
        "customer.profile.line",
        "profile_id",
    )

    def action_generate_recommendation(self):
        self.ensure_one()

        self.recommendation_line_ids.unlink()

        products = self.env["product.product"].search([
            ("product_tmpl_id.target_level", "=", self.customer_level)
        ])

        lines = []

        for product in products:
            lines.append(
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                    },
                )
            )

        self.write({
            "recommendation_line_ids": lines
        })
    
class CustomerProfileLine(models.Model):
    _name = "customer.profile.line"
    _description = "Recommendation Product"

    profile_id = fields.Many2one(
        "customer.profile",
        ondelete="cascade",
    )

    product_id = fields.Many2one(
        "product.product",
        required=True,
    )

    product_template_id = fields.Many2one(
        related="product_id.product_tmpl_id",
        store=True,
    )

    list_price = fields.Float(
        related="product_id.lst_price",
        string="Sales Price",
        store=True,
    )