from odoo import models,fields, api

class UangLainnyaWizardLine(models.TransientModel):
    _name = 'uang.lainnya.wizard.line'

    wizard_id = fields.Many2one('uang.lainnya.wizard')

    keterangan = fields.Char(string="Keterangan")
    tanggal = fields.Date(string="Tanggal")
    jenis_id = fields.Many2one(
        'jenis.transportasi',
        string="Jenis"
    )
    dari = fields.Char(string="Dari")
    ke = fields.Char(string="Ke")

    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )

    amount = fields.Monetary(
        string="Amount",
        currency_field='currency_id'
    )


class UangLainnyaWizard(models.TransientModel):
    _name = 'uang.lainnya.wizard'

    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )

    line_ids = fields.One2many(
        'uang.lainnya.wizard.line',
        'wizard_id'
    )

    total = fields.Monetary(
        string="Total",
        compute="_compute_total",
        currency_field='currency_id'
    )

    @api.depends('line_ids.amount')
    def _compute_total(self):
        for rec in self:
            rec.total = sum(rec.line_ids.mapped('amount'))

    def action_confirm(self):
        self.ensure_one()

        parent = self.env['usulan.up.country'].browse(
            self.env.context.get('active_id')
        )

        parent.uang_lainnya_line_ids.unlink()

        parent.write({
            'uang_lainnya_line_ids': [
                (0, 0, {
                    'tanggal': l.tanggal,
                    'jenis_id': l.jenis_id.id,
                    'dari': l.dari,
                    'ke': l.ke,
                    'keterangan': l.keterangan,
                    'amount': l.amount,
                }) for l in self.line_ids
            ]
        })

        return {'type': 'ir.actions.act_window_close'}