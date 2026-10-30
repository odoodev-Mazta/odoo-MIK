from odoo import models,fields,api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    profile_id = fields.One2many(
        "customer.profile",
        "partner_id",
    )