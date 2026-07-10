from odoo import models, fields


class StockMove(models.Model):
    _inherit = 'stock.move'

    date_estimasi = fields.Date(string='Tanggal Estimasi')
    jenis_product = fields.Selection([
        ('lokal', 'Lokal'),
        ('import', 'Import'),
    ], string='Jenis Produk')
    kemasan = fields.Selection([
        ('jar', 'Jar'),
        ('tube', 'Tube'),
        ('sachet', 'Sachet'),
        ('botol', 'Botol'),
        ('pump', 'Tube Pump'),
    ], string='Kemasan')
    ukuran = fields.Char(string='Ukuran')
    product_hna = fields.Float(string='HNA')
    diskon = fields.Float(string='Diskon (%)')