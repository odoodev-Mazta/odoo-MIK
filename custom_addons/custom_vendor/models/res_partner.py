from odoo import models,fields,api
from odoo.exceptions import ValidationError

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
    ], string="Marketplace")  # wajib hanya untuk vendor online, lihat _check_marketplace

    nama_bank = fields.Char(string="Nama Bank", readonly=False)
    nomor_rek = fields.Char(string="No. Rekening", readonly=False)

    @api.constrains('status_vendor', 'marketplace')
    def _check_marketplace(self):
        for partner in self:
            if partner.status_vendor == 'online' and not partner.marketplace:
                raise ValidationError("Marketplace wajib diisi untuk vendor Online.")
