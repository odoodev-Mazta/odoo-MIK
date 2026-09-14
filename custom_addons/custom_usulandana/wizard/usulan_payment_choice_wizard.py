from odoo import models, fields
from odoo.exceptions import UserError


class UsulanPaymentChoiceWizard(models.TransientModel):
    _name = 'usulan.payment.choice.wizard'
    _description = 'Pilih Metode Pembayaran Tagihan'

    schedule_id = fields.Many2one(
        'usulan.payment.schedule',
        string='Jadwal Termin',
        required=True
    )

    vendor_bill_id = fields.Many2one(
        'account.move',
        related='schedule_id.vendor_bill_id',
        readonly=True
    )

    payment_choice = fields.Selection([
        ('vendor_bill', 'Vendor Bill'),
        ('journal_entry', 'Journal Entry'),
        ('bank_payment', 'Bank Payment'),
    ], string='Pilihan Pembayaran',
       required=True,
       default='vendor_bill')

    bank_journal_id = fields.Many2one(
        'account.journal',
        string='Bank',
        domain=[('type', '=', 'bank')]
    )

    def action_confirm(self):
        self.ensure_one()

        # ==========================================
        # 1. VENDOR BILL
        # ==========================================

        if self.payment_choice == 'vendor_bill':

            if not self.schedule_id.vendor_bill_id:
                self.schedule_id._create_automated_vendor_bill_for_plan(
                    self.schedule_id
                )

            return {
                'name': 'Tagihan Vendor',
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': self.schedule_id.vendor_bill_id.id,
                'target': 'current',
            }

        # ==========================================
        # 2. JOURNAL ENTRY
        # ==========================================

        elif self.payment_choice == 'journal_entry':

            usulan_id = False

            if self.schedule_id.line_id:
                usulan_id = (
                    self.schedule_id.line_id.usulan_id.id
                )

            elif self.schedule_id.plan_payment_id.usulan_dana_id:
                usulan_id = (
                    self.schedule_id.plan_payment_id
                    .usulan_dana_id.id
                )

            return {
                'name': 'Journal Entry Manual',
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'view_mode': 'form',
                'context': {
                    'default_move_type': 'entry',
                    'default_usulan_dana_id': usulan_id,
                    'default_ref': (
                        f"Pelunasan Termin "
                        f"{self.schedule_id.plan_payment_id.name}"
                    )
                },
                'target': 'current',
            }

        # ==========================================
        # 3. BANK PAYMENT
        # ==========================================
        elif self.payment_choice == 'bank_payment':

            if not self.bank_journal_id:
                raise UserError(
                    "Silakan pilih Bank terlebih dahulu."
                )

            schedule = self.schedule_id

            # Validasi nominal
            if schedule.amount <= 0:
                raise UserError(
                    "Nominal pembayaran harus lebih dari 0."
                )

            # Jangan buat payment dua kali
            if schedule.payment_id:
                return {
                    'name': 'Pembayaran Bank',
                    'type': 'ir.actions.act_window',
                    'res_model': 'account.payment',
                    'view_mode': 'form',
                    'res_id': schedule.payment_id.id,
                    'target': 'current',
                }

            # Ambil usulan dana
            usulan = False
            if schedule.line_id:
                usulan = schedule.line_id.usulan_id

            elif schedule.plan_payment_id:
                usulan = schedule.plan_payment_id.usulan_dana_id

            if not usulan:
                raise UserError(
                    "Data Usulan Dana tidak ditemukan."
                )

            if not usulan.vendor_id:
                raise UserError(
                    "Vendor belum dipilih pada Usulan Dana."
                )

            # Ambil payment method bank
            payment_method_line = self.bank_journal_id.outbound_payment_method_line_ids[:1]

            if not payment_method_line:
                raise UserError(
                    f"Jurnal Bank '{self.bank_journal_id.name}' "
                    "belum memiliki metode pembayaran Outbound."
                )

            # Buat Bank Payment
            payment = self.env['account.payment'].create({
                'payment_type': 'outbound',
                'partner_type': 'supplier',
                'partner_id': usulan.vendor_id.id,
                'amount': schedule.amount,
                'currency_id': self.env.company.currency_id.id,
                'date': fields.Date.context_today(self),
                'journal_id': self.bank_journal_id.id,
                'payment_method_line_id': payment_method_line.id,
                'memo': f"Pembayaran {usulan.name} - Termin {schedule.amount_percentage}%",
            })

            # Posting pembayaran
            payment.action_post()

            # Simpan hubungan payment
            schedule.write({
                'payment_id': payment.id,
                'state': 'paid',
                'actual_payment_date': fields.Date.context_today(self),
            })

            return {
                'name': 'Pembayaran Bank',
                'type': 'ir.actions.act_window',
                'res_model': 'account.payment',
                'view_mode': 'form',
                'res_id': payment.id,
                'target': 'current',
            }