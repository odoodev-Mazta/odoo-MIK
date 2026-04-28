from odoo import models,fields,api


class UsulanPaymentWizard(models.TransientModel):
    _name = 'usulan.payment.wizard'
    _description = 'Wizard Termin Pembayaran'

    line_id = fields.Many2one('usulan.usulan.dana.line', string='Line Item')
    total_amount = fields.Monetary(string='Total Tagihan', currency_field='currency_id', readonly=True)
    currency_id = fields.Many2one('res.currency', related='line_id.currency_id')

    payment_type = fields.Selection([
        ('full', 'Lunas (1x Pembayaran)'),
        ('installment', 'Termin (Berkali-kali)')
    ], string='Tipe Pembayaran', default='full', required=True)

    is_initialized = fields.Boolean(default=False)
    installment_count = fields.Integer(string='Jumlah Termin', default=2)
    wizard_line_ids = fields.One2many('usulan.payment.wizard.line', 'wizard_id', string='Detail Termin')

    @api.onchange('payment_type', 'installment_count')
    def _onchange_generate_lines(self):
        # JIKA ini adalah pemanggilan pertama saat pop-up dibuka,
        # dan sudah ada data yang dimuat dari context, JANGAN RESET.
        if not self.is_initialized:
            self.is_initialized = True
            if self.wizard_line_ids:
                return

        # Logika reset hanya berjalan jika user benar-benar mengubah angka setelah pop-up terbuka
        lines = [(5, 0, 0)]
        if self.payment_type == 'full':
            lines.append((0, 0, {
                'date_payment': fields.Date.context_today(self),
                'amount_percentage': 100.0,
                'amount': self.total_amount
            }))
            self.installment_count = 1
        elif self.payment_type == 'installment' and self.installment_count > 0:
            amount_per_term = self.total_amount / self.installment_count
            pct_per_term = 100.0 / self.installment_count
            for i in range(self.installment_count):
                lines.append((0, 0, {
                    'date_payment': fields.Date.context_today(self),
                    'amount_percentage': pct_per_term,
                    'amount': amount_per_term
                }))
        self.wizard_line_ids = lines

    def action_confirm(self):
        self.ensure_one()

        # 1. Pastikan kita punya ID asli target line
        target_line = self.line_id

        # [PERBAIKAN] Gunakan cara yang sama untuk mengecek di wizard
        if not target_line or not target_line._origin.id:
            return {'type': 'ir.actions.act_window_close'}

        # Gunakan target_line._origin.id untuk memastikan kita menghapus dan membuat di ID database sungguhan
        real_line_id = target_line._origin.id

        # 2. Hapus total jadwal lama untuk line ini dari database langsung
        self.env['usulan.payment.schedule'].search([('line_id', '=', real_line_id)]).unlink()

        # 3. Create data baru satu per satu ke tabel permanen
        for w_line in self.wizard_line_ids:
            self.env['usulan.payment.schedule'].create({
                'line_id': real_line_id,
                'date_payment': w_line.date_payment,
                'amount_percentage': w_line.amount_percentage,
                'amount': w_line.amount,
            })

        # 4. Paksa refresh summary agar UI langsung terupdate
        target_line._compute_payment_summary()

        return {'type': 'ir.actions.act_window_close'}

class UsulanPaymentWizardLine(models.TransientModel):
    _name = 'usulan.payment.wizard.line'
    _description = 'Line Wizard Termin'

    wizard_id = fields.Many2one('usulan.payment.wizard')
    date_payment = fields.Date(string='Pilih Tanggal', required=True)
    amount_percentage = fields.Float(string='Persentase (%)')
    amount = fields.Monetary(string='Nominal', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='wizard_id.currency_id')

    @api.onchange('amount_percentage')
    def _onchange_percentage(self):
        """ Jika user mengubah persen, hitung ulang nominal amount """
        if self.wizard_id.total_amount and self.amount_percentage:
            # Contoh: 50% * 1.000.000 = 500.000
            self.amount = (self.amount_percentage / 100.0) * self.wizard_id.total_amount

    @api.onchange('amount')
    def _onchange_amount(self):
        """ Jika user mengetik nominal manual, hitung mundur persentasenya """
        if self.wizard_id.total_amount and self.wizard_id.total_amount > 0:
            # Contoh: (500.000 / 1.000.000) * 100 = 50%
            self.amount_percentage = (self.amount / self.wizard_id.total_amount) * 100.0