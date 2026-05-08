from odoo import models,fields


class UsulanPaymentChoiceWizard(models.TransientModel):
    _name = 'usulan.payment.choice.wizard'
    _description = 'Pilih Metode Pembayaran Tagihan'

    schedule_id = fields.Many2one('usulan.payment.schedule', string='Jadwal Termin')
    vendor_bill_id = fields.Many2one('account.move', related='schedule_id.vendor_bill_id')

    payment_choice = fields.Selection([
        ('vendor_bill', 'Vendor Bill'),
        ('journal_entry', 'Journal Entry')
    ], string='Pilihan Pembayaran', required=True, default='vendor_bill')

    def action_confirm(self):
        self.ensure_one()

        if self.payment_choice == 'vendor_bill':
            return {
                'name': 'Tagihan Vendor',
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': self.vendor_bill_id.id,
                'target': 'current',
            }

        else:
            if self.vendor_bill_id.state == 'draft':
                self.vendor_bill_id.action_post()

            usulan_id = self.schedule_id.line_id.usulan_id.id

            return {
                'name': 'Journal Entry Manual',
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'view_mode': 'form',
                'context': {
                    'default_move_type': 'entry',
                    'default_usulan_dana_id': usulan_id,
                    'default_ref': f"Pelunasan Termin {self.schedule_id.plan_payment_id.name}"
                },
                'target': 'current',
            }