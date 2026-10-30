from odoo import models, fields

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    custom_notes = fields.Char(string='Custom Notes')