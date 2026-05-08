from odoo import models, api, fields, exceptions


class AccountMove(models.Model):
    _inherit = 'account.move'

    usulan_dana_id = fields.Many2one('usulan.usulan.dana', string='UD Terkait')

    def action_post(self):
        res = super(AccountMove, self).action_post()

        for move in self:
            if move.move_type == 'entry' and move.usulan_dana_id:
                usulan = move.usulan_dana_id

                unpaid_bills = usulan.line_ids.mapped('payment_schedule_ids.vendor_bill_id').filtered(
                    lambda b: b.state == 'posted' and b.payment_state in ('not_paid', 'partial')
                )

                for bill in unpaid_bills:
                    bill_payable_lines = bill.line_ids.filtered(
                        lambda l: l.account_id.account_type in (
                        'liability_payable', 'asset_receivable') and not l.reconciled
                    )

                    je_payable_lines = move.line_ids.filtered(
                        lambda l: l.account_id in bill_payable_lines.mapped('account_id') and not l.reconciled
                    )

                    if not je_payable_lines:
                        account_names = ", ".join(bill_payable_lines.mapped('account_id.name'))
                        raise exceptions.UserError(
                            f"GAGAL!\n"
                            f"Sistem tidak bisa melunasi Vendor Bill otomatis karena akun tidak cocok.\n"
                            f"Pastikan baris (Debit) di Journal Entry ini menggunakan akun: {account_names}"
                        )

                    for je_line in je_payable_lines:
                        if not je_line.partner_id:
                            je_line.partner_id = bill.partner_id.id

                    if bill_payable_lines and je_payable_lines:
                        (bill_payable_lines + je_payable_lines).reconcile()

                    schedules_to_update = usulan.line_ids.mapped('payment_schedule_ids').filtered(
                        lambda s: s.state != 'paid' and s.vendor_bill_id.payment_state in ('paid', 'in_payment')
                    )

                    if schedules_to_update:
                        schedules_to_update.write({
                            'state': 'paid',
                            'actual_payment_date': fields.Date.context_today(self)
                        })

                        for schedule in schedules_to_update:
                            plan = schedule.plan_payment_id
                            if plan and not plan.payment_line_ids.filtered(lambda l: l.state != 'paid'):
                                plan.write({'state': 'rilis'})

                        # Cek jika semua Plan Payment sudah rilis, jadikan Usulan Dana rilis
                        all_plans = usulan.line_ids.mapped('payment_schedule_ids.plan_payment_id')
                        if usulan.state == 'approve' and all_plans and all(p.state == 'rilis' for p in all_plans):
                            usulan.write({'state': 'rilis'})
        return res

    def _compute_payment_state(self):
        super(AccountMove, self)._compute_payment_state()

        for move in self:
            if move.move_type == 'in_invoice' and move.payment_state in ['paid', 'in_payment']:
                schedules = self.env['usulan.payment.schedule'].search([
                    ('vendor_bill_id', '=', move.id),
                    ('state', '!=', 'paid')
                ])

                if schedules:
                    payments = move._get_reconciled_payments()
                    if payments:
                        pay_date = max(payments.mapped('date'))
                    else:
                        pay_date = fields.Date.context_today(self)

                    schedules.write({
                        'state': 'paid',
                        'actual_payment_date': pay_date
                    })

                    for schedule in schedules:
                        plan = schedule.plan_payment_id
                        if plan and not plan.payment_line_ids.filtered(lambda l: l.state != 'paid'):
                            plan.write({'state': 'rilis'})

                            if plan.usulan_dana_id and plan.usulan_dana_id.state == 'approve':
                                plan.usulan_dana_id.write({'state': 'rilis'})

    # def write(self, vals):
    #     res = super(AccountMove, self).write(vals)
    #
    #     if 'payment_state' in vals:
    #         for move in self:
    #             if move.move_type in ['in_invoice', 'in_receipt'] and move.payment_state in ['paid', 'in_payment']:
    #
    #                 schedules = self.env['usulan.payment.schedule'].search([('vendor_bill_id', '=', move.id)])
    #
    #                 if schedules:
    #                     usulans = schedules.mapped('line_id.usulan_id')
    #
    #                     for usulan in usulans:
    #                         if usulan.state == 'approve':
    #                             all_bills = usulan.line_ids.mapped('payment_schedule_ids.vendor_bill_id').filtered(
    #                                 lambda b: b.state == 'posted')
    #
    #                             total_paid = sum(
    #                                 all_bills.filtered(lambda b: b.payment_state in ['paid', 'in_payment']).mapped(
    #                                     'amount_total')
    #                             )
    #
    #                             if usulan.amount_total > 0 and total_paid >= usulan.amount_total:
    #                                 usulan.write({'state': 'rilis'})
    #
    #     return res