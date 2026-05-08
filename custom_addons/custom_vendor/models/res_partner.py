from odoo import models,fields

class ResPartner(models.Model):
    _inherit = 'res.partner'
    _description = 'Addition kategori pada Contacts'

    status_vendor = fields.Selection([
        ('online', 'Online'),
        ('offline', 'Offline'),
    ], string="Online/Offline", readonly=False)

    marketplace = fields.Selection([
        ('tokopedia', 'Tokopedia'),
        ('shopee', 'Shopee'),
    ], string="Marketplace", required=True)

    nama_bank = fields.Char(string="Nama Bank", readonly=False)
    nomor_rek = fields.Char(string="No. Rekening", readonly=False)