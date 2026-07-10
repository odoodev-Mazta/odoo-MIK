from odoo import models,fields,api

class MasterDataBrand(models.Model):
    _name = 'master.data.brand'
    _description = 'Master Data Brand'
    _rec_name = 'partner_id'

    partner_id = fields.Many2one(
        'res.partner',
        required=True
    )

    line_ids = fields.One2many(
        'master.data.brand.line',
        'master_brand_id'
    )

class MasterDataBrandLine(models.Model):
    _name = 'master.data.brand.line'

    master_brand_id = fields.Many2one(
        'master.data.brand',
        ondelete='cascade'
    )

    brand = fields.Char(
        required=True
    )