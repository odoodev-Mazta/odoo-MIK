from odoo import models, fields

class StockPickingDeliveryLine(models.Model):
    _name = 'stock.picking.delivery.line'
    _description = 'Stock Picking Delivery Line'

    picking_id = fields.Many2one(
        'stock.picking',
        ondelete='cascade'
    )

    product_id = fields.Many2one(
        'product.product',
        string='Product'
    )

    product_qty = fields.Float(
        string='Request (ML)'
    )

    uom_id = fields.Many2one(
        'uom.uom',
        string='UOM'
    )

    date_estimasi = fields.Date(
        string='Date Est.'
    )

    jenis_product = fields.Selection([
        ('lokal', 'Lokal'),
        ('import', 'Import')
    ])

    kemasan = fields.Selection([
        ('jar', 'Jar'),
        ('tube', 'Tube'),
        ('sachet', 'Sachet'),
        ('botol', 'Botol'),
        ('pump', 'Tube Pump')
    ])

    ukuran = fields.Char()

    product_hna = fields.Float()

    diskon = fields.Float()

    total_value = fields.Float()