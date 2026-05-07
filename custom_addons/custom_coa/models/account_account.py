from odoo import models,fields,api

class AccountAccount(models.Model):
    _inherit = 'account.account'

    is_header = fields.Boolean(
        string="Akun Header?",
        default=False,
        help="Centang jika ini adalah akun header/parent. Akun ini tidak akan muncul saat pengisian Journal Entries."
    )