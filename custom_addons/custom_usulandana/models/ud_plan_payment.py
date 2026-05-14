from odoo import models,fields,api

class UsulanPlanPayment(models.Model):
    _name = 'usulan.plan.payment'
    _description = 'Plan Payment'
    _order = 'create_date desc'

    name = fields.Char(string='No. Plan Payment', readonly=True, copy=False, default='New')
    usulan_dana_id = fields.Many2one('usulan.usulan.dana', string='Source Usulan Dana', readonly=True)
    usulan_up_country_id = fields.Many2one(
        'usulan.up.country',
        string='Source Up Country'
    )
    department_id = fields.Many2one('hr.department', string='Departemen', readonly=True)
    description = fields.Text(string='Keterangan Usulan', readonly=True)
    state = fields.Selection([
        ('menggantung', 'Menggantung'),
        ('plan_payment', 'Plan Payment'),
        ('reschedule', 'Reschedule Payment'),
        ('cancel', 'Cancelled'),
        ('rilis', 'Rilis')
    ], string='Status', default='menggantung', tracking=True)
    payment_line_ids = fields.One2many('usulan.payment.schedule', 'plan_payment_id', string='Termin Pembayaran')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    amount_total = fields.Monetary(string='Total Keseluruhan', compute='_compute_progress', store=True)
    payment_progress = fields.Char(string='Progres Bayar', compute='_compute_progress', store=True)
    vendor_bill_id = fields.Many2one('account.move', string='Vendor Bill Terkait', readonly=True)
    mou_id = fields.Many2one('draft.maklon', string='No. MOU', domain=[('state', '=', 'mou')])

    @api.depends('payment_line_ids.amount', 'payment_line_ids.state')
    def _compute_progress(self):
        for record in self:
            # 1. Hitung Total Uang
            record.amount_total = sum(record.payment_line_ids.mapped('amount'))

            # 2. Hitung Progres (Berapa termin yang sudah 'paid')
            total_termin = len(record.payment_line_ids)
            paid_termin = len(record.payment_line_ids.filtered(lambda l: l.state == 'paid'))

            if total_termin > 0:
                record.payment_progress = f"{paid_termin}/{total_termin} Termin Lunas"
            else:
                record.payment_progress = "Belum diset"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('usulan.plan.payment') or 'PP/New'
        return super().create(vals_list)

    def action_confirm_plan(self):
        self.state = 'plan_payment'

    def action_reschedule(self):
        self.state = 'reschedule'

    def action_cancel(self):
        for record in self:
            record.state = 'cancel'

            schedules_with_bill = record.payment_line_ids.filtered(lambda l: l.vendor_bill_id)

            for schedule in schedules_with_bill:
                bill = schedule.vendor_bill_id

                if bill.state == 'posted':
                    bill.button_draft()

                if bill.state != 'cancel':
                    bill.button_cancel()

    def action_view_payment_schedules(self):
        """ Membuka pop-up kalender untuk mengisi rencana bayar """
        self.ensure_one()
        view_id = self.env.ref('custom_usulandana.view_plan_payment_quick_date_form').id

        return {
            'name': 'Set Tanggal Rencana Bayar',
            'type': 'ir.actions.act_window',
            'res_model': 'usulan.plan.payment',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'view_id': view_id,
        }

    def action_close_dialog(self):
        """ Menutup pop-up. Odoo akan otomatis melakukan Save sebelum fungsi ini dijalankan """
        return {'type': 'ir.actions.act_window_close'}