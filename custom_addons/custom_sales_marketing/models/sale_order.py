from odoo import models, fields

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    marketing_sequence = fields.Char(
        string='No. PO Produksi',
        copy=False,
        index=True,
    )