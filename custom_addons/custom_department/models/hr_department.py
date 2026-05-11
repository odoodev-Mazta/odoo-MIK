from odoo import models,fields

class HrDepartment(models.Model):
    _inherit = 'hr.department'
    _description = 'Additional field in Department'

    subkode = fields.Char(string="Kode Departemen")

    jenis_surat_ids = fields.One2many(
        'jenis.surat.dept',
        'department_id',
        string="Jenis Surat"
    )