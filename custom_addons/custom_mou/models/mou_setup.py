from odoo import models,fields,api

class MouSetupTransaction(models.Model):
    _name = 'mou.setup'
    _description = 'Setup Transaksi MOU Sementara (Admin Only)'
    _order = 'date desc, id desc'

    name = fields.Char(string='No. Transaksi', required=True, help="Misal: INV-011/MIK/05/2025")
    mou_id = fields.Many2one(
        'draft.maklon',
        string='No. MOU',
        required=True,
        domain=[('state', '=', 'mou')]
    )
    pelanggan = fields.Char(string='Pelanggan', related='mou_id.nama_cust.name', store=True)
    date = fields.Date(string='Accounting Date', required=True, default=fields.Date.context_today)
    # coa_id = fields.Many2one('account.account', string='COA')
    keterangan = fields.Char(string='Keterangan')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.company.currency_id.id)

    state = fields.Selection([
        ('biaya_registrasi', 'Biaya Registrasi'),
        ('dp', 'DP'),
        ('nie', 'NIE'),
        ('pengadaan', 'Pengadaan')
    ], string='Tahapan Progress', default='biaya_registrasi', required=True)

    # FIELD STATE BIAYA REGISTRASI
    reg_due_date = fields.Date(string='Due Date Registrasi')
    reg_payment_date = fields.Date(string='Tanggal Payment Registrasi')
    reg_nilai = fields.Monetary(string='Nilai Bayar Registrasi', currency_field='currency_id')

    # FIELD STATE DP
    dp_due_date = fields.Date(string='Due Date DP')
    dp_payment_date = fields.Date(string='Tanggal Payment DP')
    dp_nilai = fields.Monetary(string='Nilai Bayar DP', currency_field='currency_id')

    # FIELD STATE NIE
    nie_due_date = fields.Date(string='Due Date NIE')
    nie_payment_date = fields.Date(string='Tanggal Payment NIE')
    nie_nilai = fields.Monetary(string='Nilai Bayar NIE', currency_field='currency_id')

    # FIELD STATE PENGADAAN
    peng_due_date = fields.Date(string='Due Date Pengadaan')
    peng_payment_date = fields.Date(string='Tanggal Payment Pengadaan')
    peng_nilai = fields.Monetary(string='Nilai Bayar Pengadaan', currency_field='currency_id')
    is_free = fields.Boolean(string="Free", readonly=False)

    @api.onchange('is_free')
    def _onchange_is_free(self):
        for rec in self:
            if rec.is_free:
                rec.reg_nilai = 0.0
                rec.dp_nilai = 0.0
                rec.nie_nilai = 0.0
                rec.peng_nilai = 0.0


    def action_set_registrasi(self):
        for rec in self:
            rec.state = 'biaya_registrasi'

    def action_set_dp(self):
        for rec in self:
            rec.state = 'dp'

    def action_set_nie(self):
        for rec in self:
            rec.state = 'nie'

    def action_set_pengadaan(self):
        for rec in self:
            rec.state = 'pengadaan'

    @api.model_create_multi
    def create(self, vals_list):
        """Terpicu otomatis saat pertama kali data di-Save"""
        records = super(MouSetupTransaction, self).create(vals_list)

        records._sync_to_container()
        return records

    def write(self, vals):
        """Terpicu otomatis setiap kali ada perubahan data (Edit)"""
        res = super(MouSetupTransaction, self).write(vals)

        self._sync_to_container()
        return res

    def _sync_to_container(self):
        """Fungsi Inti: Cari Container, kalau tidak ada langsung buat (Auto-Create)"""
        for rec in self:
            if not rec.mou_id:
                continue

            container = self.env['mou.container'].search([('mou_id', '=', rec.mou_id.id)], limit=1)

            vals = {
                'mou_id': rec.mou_id.id,
                'reg_due_date': rec.reg_due_date,
                'reg_actual_date': rec.reg_payment_date,
                'reg_nilai': rec.reg_nilai,
                'dp_due_date': rec.dp_due_date,
                'dp_actual_date': rec.dp_payment_date,
                'dp_nilai': rec.dp_nilai,
                'nie_due_date': rec.nie_due_date,
                'nie_actual_date': rec.nie_payment_date,
                'nie_nilai': rec.nie_nilai,
                'peng_due_date': rec.peng_due_date,
                'peng_actual_date': rec.peng_payment_date,
                'peng_nilai': rec.peng_nilai,
            }

            if container:
                container.write(vals)
            else:
                self.env['mou.container'].create(vals)