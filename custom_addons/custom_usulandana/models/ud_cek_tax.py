from odoo import models,fields,api

class UsulanDanaTax(models.Model):
    _name = 'usulan.dana.tax'
    _rec_name = 'usulan_dana_id'

    name = fields.Char()
    usulan_dana_id = fields.Many2one('usulan.usulan.dana')

    line_ids = fields.One2many(
        'usulan.dana.tax.line',
        'tax_id'
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done')
    ])

    def action_validate(self):
        for record in self:
            for line in record.line_ids:
                if not line.usulan_line_id:
                    continue

                usulan_line = line.usulan_line_id

                new_price = (
                    line.final_amount / usulan_line.quantity
                    if usulan_line.quantity else 0
                )

                usulan_line.write({
                    'pph_id': line.pph_id.id,
                    'tax_amount': line.tax_amount,
                    'final_amount': line.final_amount,
                    'price_unit': new_price,
                })

                for schedule in usulan_line.payment_schedule_ids:
                    schedule.amount = (
                            line.final_amount *
                            (schedule.amount_percentage / 100.0)
                    )

            record.state = 'done'
            record.usulan_dana_id.write({
                'state': 'plan_payment'
            })

class UsulanDanaTaxLine(models.Model):
    _name = 'usulan.dana.tax.line'

    tax_id = fields.Many2one('usulan.dana.tax')

    usulan_line_id = fields.Many2one(
        'usulan.usulan.dana.line'
    )

    description = fields.Char()

    original_amount = fields.Float()

    pph_id = fields.Many2one(
        'pph.setup'
    )

    tax_amount = fields.Float()

    final_amount = fields.Float(
        compute='_compute_final',
        store=True
    )

    @api.depends('original_amount', 'pph_id', 'pph_id.kategori',
                 'pph_id.percent_value', 'pph_id.fixed_value')
    def _compute_final(self):
        for line in self:
            tax = 0.0
            final = line.original_amount

            if line.pph_id:
                if line.pph_id.kategori == '%':

                    tax = (
                            line.original_amount *
                            line.pph_id.percent_value / 100
                    )
                elif line.pph_id.kategori == 'value':
                    tax = line.pph_id.fixed_value
                final = line.original_amount + tax
            line.tax_amount = tax
            line.final_amount = final