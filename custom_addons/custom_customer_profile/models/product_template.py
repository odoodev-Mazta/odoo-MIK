from odoo import models,fields,api

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    target_level = fields.Selection([
        ('low','Low'),
        ('middle','Middle'),
        ('high','High')
    ])