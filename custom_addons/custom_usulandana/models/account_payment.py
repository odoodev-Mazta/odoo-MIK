from odoo import models, fields


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def action_post(self):
        res = super().action_post()

        Schedule = self.env['usulan.payment.schedule']

        for payment in self:

            schedules = Schedule.search([
                ('payment_id', '=', payment.id)
            ])

            schedules.write({
                'state': 'paid',
                'actual_payment_date': payment.date,
            })

        return res