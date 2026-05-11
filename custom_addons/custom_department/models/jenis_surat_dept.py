from odoo import models,fields

class JenisSuratDept(models.Model):
    _name = 'jenis.surat.dept'
    _description = 'Jenis Surat Dept Line'

    department_id = fields.Many2one(
        'hr.department',
        string="Department",
        ondelete='cascade'
    )

    name = fields.Char(string="Nama Jenis Surat")
    code = fields.Char(string="Kode Surat")
    module_id = fields.Many2one(
        'ir.module.module',
        string='Modul',
        required=True,
        domain="[('state', '=', 'installed')]",
        ondelete = 'cascade'
    )