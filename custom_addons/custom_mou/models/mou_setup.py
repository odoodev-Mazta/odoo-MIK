from odoo import models, fields, api, _


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
    keterangan = fields.Char(string='Keterangan')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.company.currency_id.id)

    state = fields.Selection([
        ('biaya_registrasi', 'Biaya Registrasi'),
        ('dp', 'DP'),
        ('nie', 'NIE'),
        ('pengadaan', 'Pengadaan'),
        ('bp', 'Balance Payment'),
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

    # FIELD STATE BP (Balance Payment)
    bp_due_date = fields.Date(string='Due Date BP')
    bp_payment_date = fields.Date(string='Tanggal Payment BP')
    bp_nilai = fields.Monetary(string='Nilai Bayar BP', currency_field='currency_id')

    is_free = fields.Boolean(string="Free", readonly=False)

    @api.onchange('is_free')
    def _onchange_is_free(self):
        for rec in self:
            if rec.is_free:
                rec.reg_nilai = 0.0
                rec.dp_nilai = 0.0
                rec.nie_nilai = 0.0
                rec.peng_nilai = 0.0
                rec.bp_nilai = 0.0

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

    def action_set_bp(self):
        for rec in self:
            rec.state = 'bp'

    # ────────────────────────────────────────────────────────────────────
    # ORM Overrides
    # ────────────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        """Terpicu otomatis saat pertama kali data di-Save"""
        records = super(MouSetupTransaction, self).create(vals_list)

        records._sync_to_container()

        # Kalau langsung dibuat dalam kondisi lunas (mis. is_free dicentang
        # atau reg_payment_date langsung diisi saat create), trigger juga.
        for rec in records:
            if rec.state == 'biaya_registrasi' and (rec.reg_payment_date or rec.is_free):
                rec._auto_create_registrasi_and_design()

        return records

    def write(self, vals):
        """Terpicu otomatis setiap kali ada perubahan data (Edit)"""
        # Simpan status lunas SEBELUM diupdate, khusus record yang statenya
        # biaya_registrasi — supaya bisa deteksi transisi belum-lunas -> lunas.
        paid_before = {
            rec.id: bool(rec.reg_payment_date) or rec.is_free
            for rec in self
            if rec.state == 'biaya_registrasi'
        }

        res = super(MouSetupTransaction, self).write(vals)

        self._sync_to_container()

        if 'reg_payment_date' in vals or 'is_free' in vals or 'state' in vals:
            for rec in self:
                if rec.state != 'biaya_registrasi':
                    continue
                now_paid = bool(rec.reg_payment_date) or rec.is_free
                if now_paid and not paid_before.get(rec.id, False):
                    rec._auto_create_registrasi_and_design()

        return res

    def _sync_to_container(self):
        """Hanya sync field milik state record ini sendiri ke container,
        supaya stage lain tidak ke-overwrite jadi None."""

        STATE_FIELD_MAP = {
            'biaya_registrasi': [
                ('reg_due_date', 'reg_due_date'),
                ('reg_payment_date', 'reg_actual_date'),
                ('reg_nilai', 'reg_nilai'),
            ],
            'dp': [
                ('dp_due_date', 'dp_due_date'),
                ('dp_payment_date', 'dp_actual_date'),
                ('dp_nilai', 'dp_nilai'),
            ],
            'nie': [
                ('nie_due_date', 'nie_due_date'),
                ('nie_payment_date', 'nie_actual_date'),
                ('nie_nilai', 'nie_nilai'),
            ],
            'pengadaan': [
                ('peng_due_date', 'peng_due_date'),
                ('peng_payment_date', 'peng_actual_date'),
                ('peng_nilai', 'peng_nilai'),
            ],
            'bp': [
                ('bp_due_date', 'bp_due_date'),
                ('bp_payment_date', 'bp_actual_date'),
                ('bp_nilai', 'bp_nilai'),
            ],
        }

        for rec in self:
            if not rec.mou_id:
                continue

            container = self.env['mou.container'].search(
                [('mou_id', '=', rec.mou_id.id)], limit=1
            )

            vals = {'mou_id': rec.mou_id.id}
            for setup_field, container_field in STATE_FIELD_MAP.get(rec.state, []):
                vals[container_field] = getattr(rec, setup_field)

            if container:
                container.write(vals)
            else:
                self.env['mou.container'].create(vals)

    # ────────────────────────────────────────────────────────────────────
    # Auto-create Registrasi Brand + Design (saat Biaya Registrasi lunas)
    # ────────────────────────────────────────────────────────────────────

    def _auto_create_registrasi_and_design(self):
        """
        Dipanggil otomatis saat Biaya Registrasi (state == 'biaya_registrasi')
        baru saja lunas (reg_payment_date terisi, atau is_free = True).
        Membuat record registrasi.brand + design.usulan supaya langsung
        muncul di list view masing-masing modul — user tinggal lengkapi
        dokumen/detail, tidak perlu create manual.
        """
        self.ensure_one()
        mou = self.mou_id
        if not mou:
            return

        # ── 1. Auto-create Registrasi Brand ─────────────────────────────
        existing_brand = self.env['registrasi.brand'].search(
            [('mou_id', '=', mou.id)], limit=1
        )
        if not existing_brand:
            new_brand = self.env['registrasi.brand'].create({
                'client_id': mou.nama_cust.id if mou.nama_cust else False,
                'mou_id': mou.id,
                'brand_name': mou.brand or mou.draft_name or _('Belum diisi'),
                # Tidak ada field "brand owner" resmi di draft.maklon,
                # sementara diisi nama customer — WAJIB dicek/diedit user.
                'brand_owner': mou.nama_cust.name if mou.nama_cust else _('Belum diisi'),
                'account_option': 'client',
                'state': 'draft',
            })
            new_brand.message_post(
                body=_(
                    'Record dibuat otomatis karena Biaya Registrasi MOU %s sudah lunas. '
                    'Silakan cek Brand Owner & upload dokumen yang diperlukan.'
                ) % (mou.draft_name or mou.id)
            )
            new_brand.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_('Lengkapi dokumen registrasi brand'),
                note=_('Biaya registrasi sudah lunas. Cek Brand Owner & upload 4 dokumen yang diperlukan.'),
            )

        # ── 2. Auto-create Design Usulan ─────────────────────────────────
        existing_design = self.env['design.usulan'].search(
            [('mou_id', '=', mou.id)], limit=1
        )
        if not existing_design:
            new_design = self.env['design.usulan'].create({
                'partner_id': mou.nama_cust.id if mou.nama_cust else False,
                'mou_id': mou.id,
                'brand': mou.brand or mou.draft_name,
                'state': 'draft',
            })
            new_design.message_post(
                body=_(
                    'Form design dibuat otomatis karena Biaya Registrasi MOU %s sudah lunas.'
                ) % (mou.draft_name or mou.id)
            )