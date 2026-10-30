from odoo import models, fields, api

class AgreementTemplate(models.Model):
    _name = 'agreement.template'
    _description = 'Template MOU'

    name = fields.Char(string="Judul MOU", readonly=False)
    is_active = fields.Boolean(default=True)

    # Field pasal
    pasal_1 = fields.Html(string="Pasal 1: Maksud dan Tujuan", sanitize=True, strip_style=False)
    pasal_2 = fields.Html(string="Pasal 2: Ruang Lingkup", sanitize=True, strip_style=False)
    pasal_3 = fields.Html(string="Pasal 3: Nilai Kontrak", sanitize=True, strip_style=False)