from odoo import models,fields,api

class UsulanPaymentScheduleHeader(models.Model):
    _name = 'usulan.payment.schedule.header'
    _description = "Termin Bayar Per Usulan Dana"

    usulan_id = fields.Many2one(
        'usulan.usulan.dana',
        string='Usulan Dana',
        ondelete='cascade',
        required=True
    )
    date_payment = fields.Date(string='Tanggal Bayar', required=True)
    amount_percentage = fields.Float(string='Persentase (%)', digits=(5, 2))
    amount = fields.Monetary(
        string='Jumlah (IDR)',
        currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='usulan_id.currency_id',
        store=True
    )
    note = fields.Char(string='Keterangan')
    plan_payment_id = fields.Many2one(
        'usulan.plan.payment',
        string='Plan Payment'
    )
    vendor_bill_id = fields.Many2one(
        'account.move',
        string='Vendor Bill'
    )