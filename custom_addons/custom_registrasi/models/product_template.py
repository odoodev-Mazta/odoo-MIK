from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    registrasi_nie_number = fields.Char(string='No. NIE', copy=False, index=True)
