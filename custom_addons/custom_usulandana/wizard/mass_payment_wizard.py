from odoo import models,fields,exceptions

class UsulanMassPaymentWizard(models.TransientModel):
    _name = 'usulan.mass.payment.wizard'
    _description = 'Wizard Gabung Plan Payment'

    payment_date = fields.Date(string='Tanggal Pembayaran', required=True)

    def action_create_merged_bill(self):
        plan_ids = self.env.context.get('active_ids')
        plans = self.env['usulan.plan.payment'].browse(plan_ids)
        all_schedules = plans.mapped('payment_line_ids')
        max_due_date = max(all_schedules.mapped('date_payment')) if all_schedules else self.payment_date

        vendors = plans.mapped('usulan_dana_id.vendor_id')
        if len(vendors) > 1:
            raise exceptions.UserError("Gagal! Dokumen yang digabung harus memiliki Vendor (Supplier) yang sama.")

        invoice_line_values = []
        correct_accounts = []

        for plan in plans:
            usulan = plan.usulan_dana_id
            for line in usulan.line_ids:
                dpp_per_unit = line.price_subtotal / (line.quantity or 1.0)

                invoice_line_values.append((0, 0, {
                    'name': f"[{usulan.name}] {line.item_name}",
                    'account_id': line.setup_item_id.account_id.id,
                    'quantity': line.quantity or 1,
                    'price_unit': dpp_per_unit,
                    'tax_ids': [(6, 0, line.tax_ids.ids)],
                }))
                correct_accounts.append(line.setup_item_id.account_id.id)

        usulan_pertama = plans[0].usulan_dana_id
        invoice_vals = {
            'move_type': 'in_invoice',
            'currency_id': usulan_pertama.currency_id.id,
            'invoice_date': self.payment_date,
            'invoice_date_due': max_due_date,
            'ref': 'Tagihan Gabungan Usulan Dana',
            'partner_id': vendors[0].id,
            'invoice_line_ids': invoice_line_values,
        }

        bill = self.env['account.move'].with_context(
            default_currency_id=usulan_pertama.currency_id.id
        ).sudo().create(invoice_vals)

        all_new_attachment_ids = []

        for plan in plans:
            usulan = plan.usulan_dana_id
            if usulan.attachment_ids:
                for att in usulan.attachment_ids:
                    new_att = self.env['ir.attachment'].sudo().create({
                        'name': f"[{usulan.name}] {att.name}",
                        'type': att.type,
                        'datas': att.datas,
                        'mimetype': att.mimetype,
                        'res_model': 'account.move',
                        'res_id': bill.id,
                        'company_id': bill.company_id.id,
                    })
                    all_new_attachment_ids.append(new_att.id)

        if all_new_attachment_ids:
            bill.message_post(
                body=f"{len(all_new_attachment_ids)} Dokumen pendukung dari Usulan Dana.",
                attachment_ids=all_new_attachment_ids
            )
            bill.write({
                'message_main_attachment_id': all_new_attachment_ids[0]
            })

        bill.write({'currency_id': usulan_pertama.currency_id.id})
        for index, move_line in enumerate(bill.invoice_line_ids):
            if index < len(correct_accounts) and correct_accounts[index]:
                move_line.write({'account_id': correct_accounts[index]})

        for plan in plans:
            unbilled_lines = plan.payment_line_ids.filtered(lambda l: not l.vendor_bill_id)

            unbilled_lines.with_context(skip_auto_bill=True).write({
                'plan_payment_date': self.payment_date,
                'vendor_bill_id': bill.id
            })

            plan.state = 'plan_payment'

        return {
            'name': 'Plan Payment Gabungan',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': bill.id,
            'target': 'current',
        }