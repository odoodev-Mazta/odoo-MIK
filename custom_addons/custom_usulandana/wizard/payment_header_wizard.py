from odoo import models, fields, api, exceptions


class UsulanPaymentHeaderWizard(models.TransientModel):
    _name = 'usulan.payment.header.wizard'
    _description = 'Wizard Termin Pembayaran Per Usulan Dana'

    usulan_id = fields.Many2one('usulan.usulan.dana', string='Usulan Dana', required=True)
    total_amount = fields.Monetary(string='Total Tagihan (IDR)', currency_field='currency_id', readonly=True)
    currency_id = fields.Many2one(
        'res.currency',
        related='usulan_id.currency_id'
    )

    payment_type = fields.Selection([
        ('full', 'Lunas (1x Pembayaran)'),
        ('installment', 'Termin (Berkali-kali)')
    ], string='Tipe Pembayaran', default='full', required=True)

    is_initialized = fields.Boolean(default=False)
    installment_count = fields.Integer(string='Jumlah Termin', default=2)
    wizard_line_ids = fields.One2many(
        'usulan.payment.header.wizard.line',
        'wizard_id',
        string='Detail Termin'
    )
    total_percentage = fields.Float(
        string='Total %',
        compute='_compute_total_percentage'
    )
    remaining_percentage = fields.Float(
        string='Sisa %',
        compute='_compute_total_percentage'
    )

    @api.depends('wizard_line_ids.amount_percentage')
    def _compute_total_percentage(self):
        for wiz in self:
            total = sum(wiz.wizard_line_ids.mapped('amount_percentage'))
            wiz.total_percentage = total
            wiz.remaining_percentage = 100.0 - total

    @api.onchange('payment_type', 'installment_count')
    def _onchange_generate_lines(self):
        if not self.is_initialized:
            self.is_initialized = True
            if self.wizard_line_ids:
                return

        lines = [(5, 0, 0)]
        if self.payment_type == 'full':
            lines.append((0, 0, {
                'date_payment': fields.Date.context_today(self),
                'amount_percentage': 100.0,
                'amount': self.total_amount,
            }))
            self.installment_count = 1
        elif self.payment_type == 'installment' and self.installment_count > 0:
            amount_per_term = self.total_amount / self.installment_count
            pct_per_term = 100.0 / self.installment_count
            for i in range(self.installment_count):
                lines.append((0, 0, {
                    'date_payment': fields.Date.context_today(self),
                    'amount_percentage': pct_per_term,
                    'amount': amount_per_term,
                }))
        self.wizard_line_ids = lines

    def action_confirm(self):
        self.ensure_one()

        # Validasi total = 100%
        total_pct = sum(self.wizard_line_ids.mapped('amount_percentage'))
        if abs(total_pct - 100.0) > 0.01:
            raise exceptions.UserError(
                f"Total persentase harus 100%. Saat ini: {total_pct:.2f}%"
            )

        usulan = self.usulan_id

        usulan.header_schedule_ids.unlink()

        for wiz_line in self.wizard_line_ids:
            self.env['usulan.payment.schedule.header'].create({
                'usulan_id': usulan.id,
                'date_payment': wiz_line.date_payment,
                'amount_percentage': wiz_line.amount_percentage,
                'amount': usulan.amount_total * (wiz_line.amount_percentage / 100.0),
                'note': wiz_line.note,
            })

        for line in usulan.line_ids:
            self.env['usulan.payment.schedule'].search([
                ('line_id', '=', line.id)
            ]).unlink()

            for wiz_line in self.wizard_line_ids:
                self.env['usulan.payment.schedule'].create({
                    'line_id': line.id,
                    'date_payment': wiz_line.date_payment,
                    'amount_percentage': wiz_line.amount_percentage,
                    'amount': line.grand_total * (wiz_line.amount_percentage / 100.0),
                })
        return {'type': 'ir.actions.act_window_close'}


class UsulanPaymentHeaderWizardLine(models.TransientModel):
    _name = 'usulan.payment.header.wizard.line'
    _description = 'Line Wizard Termin Header'

    wizard_id = fields.Many2one('usulan.payment.header.wizard', ondelete='cascade')
    date_payment = fields.Date(string='Pilih Tanggal', required=True)
    amount_percentage = fields.Float(string='Persentase (%)', default=100.0)
    amount = fields.Monetary(string='Nominal (IDR)', currency_field='currency_id', readonly=True)
    currency_id = fields.Many2one('res.currency', related='wizard_id.currency_id')
    note = fields.Char(string='Keterangan')

    @api.onchange('amount_percentage')
    def _onchange_percentage(self):
        if self.wizard_id.total_amount and self.amount_percentage:
            self.amount = (self.amount_percentage / 100.0) * self.wizard_id.total_amount