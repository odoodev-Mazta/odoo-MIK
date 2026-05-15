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
    currency_id = fields.Many2one('res.currency', related='line_id.currency_id')
    department_id = fields.Many2one('hr.department', related='line_id.usulan_id.department_id', store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('unpaid', 'Belum Dibayar'),
        ('paid', 'Sudah Dibayar')
    ], string='Status Bayar', default='unpaid')
    plan_payment_id = fields.Many2one('usulan.plan.payment', string='Plan Payment Parent', ondelete='cascade')
    actual_payment_date = fields.Date(string='Realisasi Bayar')
    vendor_bill_id = fields.Many2one('account.move', string='Vendor Bill Terkait', readonly=True)

    def write(self, vals):
        res = super(UsulanPaymentSchedule, self).write(vals)

        if 'plan_payment_date' in vals and vals.get('plan_payment_date') and not self.env.context.get('skip_auto_bill'):
            for record in self:

                if not record.vendor_bill_id:
                    record._create_automated_vendor_bill()

                    if record.plan_payment_id.state in ['menggantung', 'reschedule']:
                        record.plan_payment_id.state = 'plan_payment'
                else:
                    if record.vendor_bill_id.state == 'draft':
                        record.vendor_bill_id.write({'invoice_date': record.plan_payment_date})

                    if record.plan_payment_id.state == 'reschedule':
                        record.plan_payment_id.state = 'plan_payment'
        return res

    def _create_automated_vendor_bill(self):
        self.ensure_one()
        usulan = self.plan_payment_id.usulan_dana_id

        invoice_line_values = []
        correct_accounts = []

        if self.amount == usulan.amount_total:
            for line in usulan.line_ids:
                dpp_per_unit = line.price_subtotal / (line.quantity or 1.0)
                invoice_line_values.append((0, 0, {
                    'name': getattr(line, 'item_name', False) or line.setup_item_id.name,
                    'account_id': line.setup_item_id.account_id.id,
                    'quantity': line.quantity or 1,
                    'price_unit': line.price_unit,
                    'discount': line.discount,
                    'tax_ids': [(6, 0, line.tax_ids.ids)],
                }))
                correct_accounts.append(line.setup_item_id.account_id.id)
        else:
            first_item = usulan.line_ids[0] if usulan.line_ids else False
            termin_dpp = 0.0
            if usulan.amount_total > 0:
                persentase_termin = self.amount / usulan.amount_total
                termin_dpp = usulan.amount_dpp * persentase_termin
            else:
                termin_dpp = self.amount
            invoice_line_values.append((0, 0, {
                'name': f"Termin: {usulan.description or 'Usulan'}",
                'account_id': first_item.setup_item_id.account_id.id if first_item else False,
                'quantity': 1,
                'price_unit': termin_dpp,
                'tax_ids': [(6, 0, first_item.tax_ids.ids)] if first_item else False,
            }))
            correct_accounts.append(first_item.setup_item_id.account_id.id if first_item else False)

        tanggal_str = self.plan_payment_date.strftime("%d-%m-%Y") if self.plan_payment_date else ''
        invoice_vals = {
            'move_type': 'in_invoice',
            'invoice_date': self.plan_payment_date,
            'invoice_date_due': self.date_payment,
            'ref': f"Termin {self.plan_payment_id.name}",
            'partner_id': usulan.vendor_id.id,
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

                bill.write({
                    'message_main_attachment_id': new_attachment_ids[0]
                })

        for index, move_line in enumerate(bill.invoice_line_ids):
            if index < len(correct_accounts) and correct_accounts[index]:
                move_line.write({'account_id': correct_accounts[index]})

        self.vendor_bill_id = bill.id

    def action_pay_termin(self):
        self.ensure_one()

        if not self.vendor_bill_id:
            from odoo import exceptions
            raise exceptions.UserError(
                "Tagihan (Vendor Bill) belum terbuat. Silakan isi Tanggal Termin terlebih dahulu untuk membuatnya otomatis.")

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
        ])

        plan_payments = self.env['usulan.plan.payment'].search([])

        indo_holidays = holidays.Indonesia(years=year)

        calendar_data = []
        month_matrix = monthcalendar(year, month)

        weekly_summary = []

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

                    'payments': [{
                        'id': schedule.id,
                        'vendor': (
                            schedule.plan_payment_id.usulan_dana_id.vendor_id.name
                        ) or (
                            schedule.plan_payment_id.usulan_up_country_id.employee_id.name
                        ),
                        'amount': schedule.amount,
                        'state': schedule.plan_payment_id.state,
                        'plan_name': schedule.plan_payment_id.name,
                    } for schedule in day_schedules]
                })

            calendar_data.append(week_data)

            weekly_summary.append({
                'week': week_index,
                'amount': week_total,
            })

        return {
            'summary': {
                'menggantung': len(
                    plan_payments.filtered(
                        lambda x: x.state == 'menggantung'
                    )
                ),
                'plan_payment': len(
                    plan_payments.filtered(
                        lambda x: x.state == 'plan_payment'
                    )
                ),
                'reschedule': len(
                    plan_payments.filtered(
                        lambda x: x.state == 'reschedule'
                    )
                ),
            },
            'calendar': calendar_data,
            'weekly_summary': weekly_summary,
        }

    @api.model
    def action_open_calendar_popup(self, selected_date):
        schedules = self.search([
            ('plan_payment_date', '=', selected_date)
        ])

        line_vals = []
        for schedule in schedules:
            plan = schedule.plan_payment_id
            usulan = (
                    plan.usulan_dana_id
                    or
                    plan.usulan_up_country_id
            )

            line_vals.append((0, 0, {
                'department_id':
                    plan.department_id.id,

                'tgl_usulan':
                    usulan.tgl_usulan
                    if hasattr(usulan, 'tgl_usulan')
                    else False,

                'due_date':
                    schedule.date_payment,

                'description':
                    plan.description,

                'amount':
                    schedule.amount,

                'plan_payment_id':
                    plan.id,

                'state':
                    plan.state,
            }))
        wizard = self.env[
            'usulan.plan.payment.calendar.wizard'
        ].create({
            'selected_date': selected_date,
            'line_ids': line_vals,
        })

        return {
            'type': 'ir.actions.act_window',
            'name': f'Plan Payment {selected_date}',
            'res_model':
                'usulan.plan.payment.calendar.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }