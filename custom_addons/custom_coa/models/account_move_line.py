from odoo import models, api
from odoo.exceptions import ValidationError

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.constrains('account_id')
    def _check_account_is_not_header(self):
        for line in self:
            if line.account_id and line.account_id.is_header:
                raise ValidationError(f"Validasi Gagal: Anda tidak dapat menjurnal menggunakan Akun Header ({line.account_id.code} - {line.account_id.name}). Silakan pilih akun anak/child.")