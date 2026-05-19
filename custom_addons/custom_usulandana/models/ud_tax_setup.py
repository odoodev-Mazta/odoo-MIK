from odoo import models,fields,api
from odoo.exceptions import ValidationError


class PphSetup(models.Model):
    _name = 'pph.setup'
    _description = 'Model untuk setup Pph Usulan Dana'
    _rec_name = 'display_name'

    name = fields.Char(string="Nama Pph", readonly=False)

    pph_type = fields.Selection([
        ('pph21', 'Pph 21'),
        ('pph23', 'Pph 23'),
        ('pph4ayat2', 'Pph 4 Ayat 2'),
    ], string="Jenis Pph", readonly=False)

    kategori = fields.Selection([
        ('%', '%'),
        ('value', 'Value'),
    ], string="Kategori", readonly=False)

    percent_value = fields.Float(string="Nilai %")
    fixed_value = fields.Monetary(string="Nilai Pajak")
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )
    active = fields.Boolean(default=True)
    display_name = fields.Char(
        compute='_compute_display_name',
        store=True
    )

    @api.constrains('kategori', 'percent_value', 'fixed_value')
    def _check_tax_value(self):
        for rec in self:
            if rec.kategori == '%':
                if rec.percent_value <= 0:
                    raise ValidationError("Nilai % harus lebih dari 0.")

                if rec.fixed_value:
                    raise ValidationError(
                        "Nilai Pajak harus kosong jika kategori Percent."
                    )

            elif rec.kategori == 'value':
                if rec.fixed_value <= 0:
                    raise ValidationError(
                        "Nilai Pajak harus lebih dari 0."
                    )

                if rec.percent_value:
                    raise ValidationError(
                        "Nilai % harus kosong jika kategori Fixed Value."
                    )

    @api.depends('pph_type', 'kategori','percent_value', 'fixed_value')
    def _compute_display_name(self):
        for rec in self:

            pph_label = dict(
                rec._fields['pph_type'].selection
            ).get(rec.pph_type)

            if rec.kategori == '%':
                rec.display_name = (
                    f"{pph_label} - {rec.percent_value}%"
                )
            else:
                rec.display_name = (
                    f"{pph_label} - Rp {rec.fixed_value:,.0f}"
                )