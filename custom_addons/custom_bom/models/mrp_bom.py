from odoo import fields, models


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    brand = fields.Char(
        string="Brand",
    )

    product_variant = fields.Char(
        string="Varian Produk",
    )