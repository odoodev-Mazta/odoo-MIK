from odoo import models, fields, api, exceptions
from odoo.exceptions import UserError
from calendar import monthcalendar
from datetime import date
import holidays
import calendar


class UsulanPaymentSchedule(models.Model):
    _name = 'usulan.payment.schedule'
    _description = 'Jadwal Pembayaran Usulan'

    line_id = fields.Many2one('usulan.usulan.dana.line', string='Line Usulan', ondelete='cascade')
    up_country_line_id = fields.Many2one(
        'usulan.up.country.line',
        string='Up Country Line'
    )
    date_payment = fields.Date(string='Tanggal Termin', required=True)
    plan_payment_date = fields.Date(string='Plan Payment')
    amount_percentage = fields.Float(string='Persentase (%)')
    amount = fields.Monetary(string='Nominal', currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency',
        compute='_compute_currency_id',
        store=True
    )
    department_id = fields.Many2one('hr.department', related='line_id.usulan_id.department_id', store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('unpaid', 'Belum Dibayar'),
        ('paid', 'Sudah Dibayar')
    ], string='Status Bayar', default='unpaid')
    plan_payment_id = fields.Many2one('usulan.plan.payment', string='Plan Payment Parent', ondelete='cascade')
    description = fields.Text(
        related='plan_payment_id.description',
        string='Keterangan',
        store=True,
        readonly=True
    )
    actual_payment_date = fields.Date(string='Realisasi Bayar')
    vendor_bill_id = fields.Many2one('account.move', string='Vendor Bill Terkait', readonly=True)

    @api.depends('line_id', 'plan_payment_id')
    def _compute_currency_id(self):
        idr = self.env['res.currency'].search([('name', '=', 'IDR')], limit=1)
        for rec in self:
            if rec.plan_payment_id:
                rec.currency_id = idr
            elif rec.line_id:
                rec.currency_id = rec.line_id.currency_id
            else:
                rec.currency_id = idr

    def write(self, vals):
        old_dates = {rec.id: rec.plan_payment_date for rec in self}
        res = super(UsulanPaymentSchedule, self).write(vals)

        if 'plan_payment_date' in vals and not self.env.context.get('skip_auto_bill'):
            plan_payment_groups = {}
            for record in self:
                if not record.plan_payment_id:
                    continue
                pid = record.plan_payment_id.id
                if pid not in plan_payment_groups:
                    plan_payment_groups[pid] = []
                plan_payment_groups[pid].append(record)

            for pid, schedules in plan_payment_groups.items():
                plan = schedules[0].plan_payment_id

                for record in schedules:
                    old_date = old_dates.get(record.id)
                    new_date = record.plan_payment_date
                    if old_date and new_date and old_date != new_date:
                        plan.state = 'reschedule'
                    # Update tanggal di bill existing jika ada
                    if record.vendor_bill_id and record.vendor_bill_id.state == 'draft':
                        record.vendor_bill_id.write({
                            'invoice_date': record.plan_payment_date,
                            'invoice_date_due': record.plan_payment_date,
                        })

        return res

    def _create_automated_vendor_bill_for_plan(self, all_schedules):
        self.ensure_one()
        usulan = self.plan_payment_id.usulan_dana_id
        plan = self.plan_payment_id

        idr_currency = self.env['res.currency'].search([('name', '=', 'IDR')], limit=1)
        if not idr_currency:
            raise exceptions.UserError("Currency IDR tidak ditemukan di sistem.")

        invoice_line_values = []
        correct_accounts = []

        def _get_account_for_line(line):
            if line.setup_item_id and line.setup_item_id.account_id:
                return line.setup_item_id.account_id.id
            if line.product_id:
                account = (
                        line.product_id.property_account_expense_id
                        or line.product_id.categ_id.property_account_expense_categ_id
                )
                if account:
                    return account.id
            default_account = self.env['account.account'].search([
                ('account_type', '=', 'expense'),
            ], limit=1)
            if default_account:
                return default_account.id
            raise exceptions.UserError(
                f"Akun (COA) tidak ditemukan untuk item "
                f"'{line.setup_item_id.name if line.setup_item_id else (line.product_id.display_name if line.product_id else 'Unknown')}'. "
                f"Pastikan item memiliki akun yang dikonfigurasi di master data."
            )

        def _get_line_name(line):
            base_name = (
                    getattr(line, 'item_name', None)
                    or (line.setup_item_id and line.setup_item_id.name)
                    or (line.product_id and line.product_id.display_name)
                    or 'Item'
            )
            if line.is_foreign_currency and line.today_rate:
                base_name += f" [{line.currency_id.name} {line.price_unit:,.2f} × {line.today_rate:,.4f}]"
            return base_name

        # ── KUNCI FIX: ambil hanya line milik schedule yang diklik ──
        # all_schedules di sini adalah self (1 schedule), jadi ambil line_id-nya saja
        lines_to_bill = all_schedules.mapped('line_id').filtered(lambda l: l.id)

        # Fallback: jika line_id kosong (misal schedule dari header/per_usulan),
        # baru gunakan semua line dari usulan
        if not lines_to_bill:
            lines_to_bill = usulan.line_ids

        schedule_pct = all_schedules[0].amount_percentage if all_schedules else 100.0
        is_full_payment = abs(schedule_pct - 100.0) < 0.01

        if is_full_payment:
            # Termin 100%: nominal penuh per item
            for line in lines_to_bill:
                account_id = _get_account_for_line(line)
                qty = line.quantity or 1.0
                price_unit_idr = line.grand_total / qty

                invoice_line_values.append((0, 0, {
                    'name': _get_line_name(line),
                    'account_id': account_id,
                    'quantity': qty,
                    'price_unit': price_unit_idr,
                    'discount': 0.0,
                    'tax_ids': [],
                }))
                correct_accounts.append(account_id)
        else:
            # Termin sebagian: nominal proporsional per item
            pct = schedule_pct / 100.0
            for line in lines_to_bill:
                account_id = _get_account_for_line(line)
                amount_for_line = line.grand_total * pct
                line_name = _get_line_name(line) + f" - Termin {int(schedule_pct)}%"

                invoice_line_values.append((0, 0, {
                    'name': line_name,
                    'account_id': account_id,
                    'quantity': 1,
                    'price_unit': amount_for_line,
                    'discount': 0.0,
                    'tax_ids': [],
                }))
                correct_accounts.append(account_id)

        invoice_vals = {
            'move_type': 'in_invoice',
            'invoice_date': self.plan_payment_date,
            'invoice_date_due': self.date_payment,
            'ref': f"Termin {plan.name} - {_get_line_name(lines_to_bill[0]) if lines_to_bill else ''}",
            'partner_id': usulan.vendor_id.id,
            'currency_id': idr_currency.id,
            'invoice_line_ids': invoice_line_values,
        }
        bill = self.env['account.move'].sudo().create(invoice_vals)

        if usulan.attachment_ids:
            new_attachment_ids = []
            for att in usulan.attachment_ids:
                new_att = self.env['ir.attachment'].sudo().create({
                    'name': att.name,
                    'type': att.type,
                    'datas': att.datas,
                    'mimetype': att.mimetype,
                    'res_model': 'account.move',
                    'res_id': bill.id,
                    'company_id': bill.company_id.id,
                })
                new_attachment_ids.append(new_att.id)
            if new_attachment_ids:
                bill.message_post(
                    body="Attachment dari Usulan Dana.",
                    attachment_ids=new_attachment_ids
                )
                bill.write({'message_main_attachment_id': new_attachment_ids[0]})

        for index, move_line in enumerate(bill.invoice_line_ids):
            if index < len(correct_accounts) and correct_accounts[index]:
                move_line.write({'account_id': correct_accounts[index]})

        for schedule in all_schedules:
            schedule.with_context(skip_auto_bill=True).vendor_bill_id = bill.id

    def action_pay_termin(self):
        self.ensure_one()

        # Buat bill jika belum ada, panggil fungsi yang sama
        if not self.vendor_bill_id:
            self._create_automated_vendor_bill_for_plan(self)

        return {
            'name': 'Pilih Metode Pembayaran',
            'type': 'ir.actions.act_window',
            'res_model': 'usulan.payment.choice.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_schedule_id': self.id,
            }
        }

    @api.model
    def get_schedule_dashboard(self, year, month):

        last_day = calendar.monthrange(year, month)[1]
        end_date = date(year, month, last_day)
        start_date = date(year, month, 1)

        schedules = self.search([
            ('plan_payment_date', '!=', False),
            ('plan_payment_date', '>=', start_date),
            ('plan_payment_date', '<=', end_date),
            ('plan_payment_id.state', 'not in', ['rilis', 'cancel']),
        ])

        schedules = schedules.filtered(
            lambda s:
            not (
                    s.plan_payment_id.usulan_dana_id
                    and
                    s.plan_payment_id.usulan_dana_id.status_payment == 'paid'
            )
        )

        plan_payments = self.env['usulan.plan.payment'].search([])

        indo_holidays = holidays.Indonesia(years=year)

        calendar_data = []
        month_matrix = monthcalendar(year, month)

        weekly_summary = []
        weekly_plan_payment = {i: 0 for i in range(1, 6)}

        for week_index, week in enumerate(month_matrix, start=1):

            week_data = []
            week_total = 0

            for day in week:

                if day == 0:
                    week_data.append({
                        'day': '',
                        'payments': [],
                        'is_sunday': False,
                        'is_holiday': False,
                        'holiday_name': False,
                    })
                    continue

                current_date = date(year, month, day)
                is_sunday = current_date.weekday() == 6
                is_holiday = current_date in indo_holidays

                holiday_name = (
                    indo_holidays.get(current_date)
                    if is_holiday else False
                )

                day_schedules = schedules.filtered(
                    lambda x: x.plan_payment_date == current_date
                )

                week_total += sum(day_schedules.mapped('amount'))

                week_data.append({
                    'day': day,
                    'is_sunday': is_sunday,
                    'is_holiday': is_holiday,
                    'full_date': current_date.strftime('%Y-%m-%d'),
                    'holiday_name': holiday_name,
                    'payments_total': sum(day_schedules.mapped('amount')),
                    'payments_count': len(day_schedules),

                    # 'payments': [{
                    #     'id': schedule.id,
                    #     'vendor': (
                    #         schedule.plan_payment_id.usulan_dana_id.vendor_id.name
                    #     ) or (
                    #         schedule.plan_payment_id.usulan_up_country_id.employee_id.name
                    #     ),
                    #     'amount': schedule.amount,
                    #     'state': schedule.plan_payment_id.state,
                    #     'plan_name': schedule.plan_payment_id.name,
                    # } for schedule in day_schedules]
                })

            weekly_summary.append({
                'week': week_index,
                'amount': week_total,
            })

            weekly_plan_payment[week_index] = week_total

            calendar_data.append(week_data)

            weekly_summary.append({
                'week': week_index,
                'amount': week_total,
            })

            # dummy total surplus
            total_plan_payment = sum(
                weekly_plan_payment.values()
            )

            bank_balance = 0
            outstanding_receivable = 0

            total_fund = (
                    bank_balance +
                    outstanding_receivable
            )

            surplus = total_fund - total_plan_payment
            surplus_negative = surplus < 0

            # dummy progress bar rilis dan not rilis
            today_release_amount = sum(
                schedules.filtered(
                    lambda s: s.plan_payment_id.state == 'rilis'
                ).mapped('amount')
            )

            today_pending_amount = sum(
                schedules.filtered(
                    lambda s: s.plan_payment_id.state != 'rilis'
                ).mapped('amount')
            )

            total_amount = (
                today_release_amount +
                today_pending_amount
            )

            release_percentage = (
                (today_release_amount / total_amount) * 100
            ) if total_amount else 0

            pending_percentage = (
                (today_pending_amount / total_amount) * 100
            ) if total_amount else 0

        return {
            'summary': {
                'menggantung': len(plan_payments.filtered(lambda x: x.state == 'menggantung')),
                'plan_payment': len(plan_payments.filtered(lambda x: x.state == 'plan_payment')),
                'reschedule': len(plan_payments.filtered(lambda x: x.state == 'reschedule')),
            },
            'calendar': calendar_data,
            'weekly_summary': weekly_summary,
            'weekly_plan_payment': [
                {
                    'week': i,
                    'amount': weekly_plan_payment.get(i, 0),
                }
                for i in range(1, 6)
            ],
            # data dummy total surplus
            'bank_balance': bank_balance,
            'outstanding_receivable': outstanding_receivable,
            'total_plan_payment': total_plan_payment,
            'surplus': surplus,
            'surplus_negative': surplus_negative,
            'today_release_amount': today_release_amount,
            'today_pending_amount': today_pending_amount,
            'release_percentage': round(release_percentage, 2),
            'pending_percentage': round(pending_percentage, 2),
        }

    @api.model
    def action_open_calendar_popup(self, selected_date):

        schedules = self.search([
            ('plan_payment_date', '=', selected_date)
        ])

        wizard = self.env[
            'usulan.plan.payment.calendar.wizard'
        ].create({
            'selected_date': selected_date,
            'schedule_ids': [(6, 0, schedules.ids)],
        })

        view_id = self.env.ref(
            'custom_usulandana.view_calendar_plan_payment_popup'
        ).id

        return {
            'type': 'ir.actions.act_window',
            'name': f'Plan Payment {selected_date}',
            'res_model': 'usulan.plan.payment.calendar.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'views': [(view_id, 'form')],
            'target': 'new',
        }

    def action_open_plan_payment(self):
        self.ensure_one()

        view_id = self.env.ref(
            'custom_usulandana.view_plan_payment_form'
        ).id

        return {
            'type': 'ir.actions.act_window',
            'name': 'Plan Payment',
            'res_model': 'usulan.plan.payment',
            'res_id': self.plan_payment_id.id,
            'view_mode': 'form',
            'views': [(view_id, 'form')],
            'target': 'current',
        }

    def unlink(self):
        if self.env.context.get('from_reschedule_wizard'):
            raise UserError(
                "Data tidak boleh dihapus dari wizard reschedule. Hanya boleh reschedule tanggal."
            )
        return super().unlink()