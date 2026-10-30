from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'
    _description = 'Custom Partner for Additional Custom Field in Vendor'

    status = fields.Selection([
        ('online', 'ONLINE'),
        ('offline', 'OFFLINE')
    ], string='ONLINE/OFFLINE', readonly=False)
    marketplace = fields.Char(string='MARKETPLACE', readonly=False)
    pic_vendor = fields.Many2one("hr.employee", string="PIC VENDOR", readonly=False)
    bank = fields.Char(string="BANK", readonly=False)
    no_rek = fields.Char(string="NO REK", readonly=False)
    spes_lama = fields.Char(string="SPESIFIKASI LAMA", readonly=False)
    spesifikasi = fields.Many2one('product.product', string="SPESIFIKASI", readonly=False)
    klasifikasi = fields.Char(string="KLASIFIKASI VENDOR", readonly=False)