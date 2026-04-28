from odoo import models, fields, api, exceptions
from odoo.exceptions import UserError


class UsulanPaymentSchedule(models.Model):
    _name = 'usulan.payment.schedule'
    _description = 'Jadwal Pembayaran Usulan'

    line_id = fields.Many2one('usulan.usulan.dana.line', string='Line Usulan', ondelete='cascade')
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
                    'name': line.item_name or line.setup_item_id.name,
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
            raise exceptions.UserError(
                "Tagihan (Vendor Bill) belum terbuat. Silakan isi Tanggal Termin terlebih dahulu untuk membuatnya otomatis.")

        return {
            'name': 'Tagihan Terkait',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.vendor_bill_id.id,
            'target': 'current',
        }