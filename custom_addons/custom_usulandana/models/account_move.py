from odoo import models, api, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

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

    def write(self, vals):
        res = super(AccountMove, self).write(vals)

        if 'payment_state' in vals:
            for move in self:
                if move.move_type in ['in_invoice', 'in_receipt'] and move.payment_state in ['paid', 'in_payment']:

                    schedules = self.env['usulan.payment.schedule'].search([('vendor_bill_id', '=', move.id)])

                    if schedules:
                        usulans = schedules.mapped('line_id.usulan_id')

                        for usulan in usulans:
                            if usulan.state == 'approve':
                                all_bills = usulan.line_ids.mapped('payment_schedule_ids.vendor_bill_id').filtered(
                                    lambda b: b.state == 'posted')

                                total_paid = sum(
                                    all_bills.filtered(lambda b: b.payment_state in ['paid', 'in_payment']).mapped(
                                        'amount_total')
                                )

                                if usulan.amount_total > 0 and total_paid >= usulan.amount_total:
                                    usulan.write({'state': 'rilis'})

        return res