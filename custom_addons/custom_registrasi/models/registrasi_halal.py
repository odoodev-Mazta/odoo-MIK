from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta


class HalalRegistrasi(models.Model):
    _name = 'halal.registrasi'
    _description = 'Registrasi Halal Produk'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'
    _rec_name = 'name'

    # ─── Sequence / Identitas ────────────────────────────────────────────────
    name = fields.Char(
        string='Nomor Registrasi',
        copy=False,
        readonly=True,
        default=lambda self: _('Baru'),
        tracking=True,
    )

    # ─── Relasi ke Registrasi Produk & Brand ────────────────────────────────
    produk_id = fields.Many2one(
        comodel_name='registrasi.produk',
        string='Registrasi Produk (NIE)',
        domain=[('state', '=', 'nie_issued')],
        tracking=True,
        index=True,
        help='Opsional. Tautkan ke registrasi produk NIE yang sudah terbit.',
    )
    brand_registration_id = fields.Many2one(
        comodel_name='registrasi.brand',
        string='Registrasi Brand',
        related='produk_id.brand_registration_id',
        store=True,
        readonly=True,
    )
    brand_name = fields.Char(
        string='Nama Brand',
        required=True,
        tracking=True,
    )
    client_id = fields.Many2one(
        comodel_name='res.partner',
        string='Klien / Pemohon',
        required=True,
        tracking=True,
        index=True,
    )

    product_name = fields.Char(
        string='Nama Produk',
        required=True,
        tracking=True,
    )

    # ─── Tipe & Kategori Halal ───────────────────────────────────────────────
    halal_type = fields.Selection(
        selection=[
            ('lokal', 'Lokal'),
            ('import', 'Import'),
        ],
        string='Tipe Halal',
        required=True,
        tracking=True,
    )
    jenis_produk = fields.Selection(
        selection=[
            ('makanan_minuman', 'Makanan & Minuman'),
            ('kosmetik', 'Kosmetik'),
            ('obat', 'Obat-obatan'),
            ('suplemen', 'Suplemen Kesehatan'),
            ('bahan_baku', 'Bahan Baku'),
            ('lainnya', 'Lainnya'),
        ],
        string='Jenis Produk',
        required=True,
        tracking=True,
    )
    lembaga_sertifikasi = fields.Selection(
        selection=[
            ('bpjph', 'BPJPH (Badan Penyelenggara Jaminan Produk Halal)'),
            ('mui', 'MUI (Majelis Ulama Indonesia)'),
            ('luar_negeri', 'Lembaga Halal Luar Negeri'),
        ],
        string='Lembaga Sertifikasi',
        required=True,
        tracking=True,
    )
    lembaga_luar_negeri = fields.Char(
        string='Nama Lembaga (Luar Negeri)',
        tracking=True,
    )

    # ─── Nomor & Masa Berlaku Sertifikat ────────────────────────────────────
    nomor_sertifikat = fields.Char(
        string='Nomor Sertifikat Halal',
        copy=False,
        tracking=True,
    )
    tanggal_terbit = fields.Date(
        string='Tanggal Terbit Sertifikat',
        copy=False,
        tracking=True,
    )
    tanggal_expired = fields.Date(
        string='Tanggal Kadaluarsa Sertifikat',
        copy=False,
        tracking=True,
    )
    is_expired = fields.Boolean(
        string='Sudah Kadaluarsa',
        compute='_compute_is_expired',
        store=True,
    )
    sisa_hari = fields.Integer(
        string='Sisa Hari Berlaku',
        compute='_compute_is_expired',
        store=True,
    )

    # ─── Status / State ──────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('pengajuan', 'Pengajuan Dokumen'),
            ('verifikasi_internal', 'Verifikasi Internal'),
            ('submitted_lembaga', 'Diajukan ke Lembaga'),
            ('audit_halal', 'Audit Halal'),
            ('menunggu_keputusan', 'Menunggu Keputusan'),
            ('sertifikat_terbit', 'Sertifikat Terbit'),
            ('ditolak', 'Ditolak'),
            ('kadaluarsa', 'Kadaluarsa'),
        ],
        string='Status',
        default='draft',
        required=True,
        copy=False,
        tracking=True,
        index=True,
    )

    # Module Integration: registrasi_produk

    mou_id = fields.Many2one(
        comodel_name='draft.maklon',
        string='MoU Reference',
        tracking=True,
        domain=[('state', '=', 'mou')],    
        help='Required for Import category. Must be a confirmed MOU.',
    )

    # ─── SLA & Tenggat ───────────────────────────────────────────────────────
    tanggal_pengajuan = fields.Date(
        string='Tanggal Pengajuan',
        readonly=True,
        copy=False,
        tracking=True,
    )
    target_selesai = fields.Date(
        string='Target Selesai (SLA)',
        readonly=True,
        copy=False,
        tracking=True,
    )
    sla_hari = fields.Integer(
        string='SLA (Hari)',
        default=30,
        help='Estimasi hari proses sertifikasi halal.',
    )

    # ─── Persetujuan Internal ────────────────────────────────────────────────
    disetujui_regulatory = fields.Many2one(
        comodel_name='res.users',
        string='Diverifikasi oleh Regulatory',
        readonly=True,
        copy=False,
        tracking=True,
    )
    tanggal_verifikasi = fields.Datetime(
        string='Tanggal Verifikasi Internal',
        readonly=True,
        copy=False,
    )
    catatan_verifikasi = fields.Text(
        string='Catatan Verifikasi Internal',
        tracking=True,
    )

    # ─── Catatan Penolakan / Revisi ──────────────────────────────────────────
    catatan_penolakan = fields.Text(
        string='Catatan Penolakan / Revisi',
        tracking=True,
    )
    revision_counter = fields.Integer(
        string='Jumlah Revisi',
        default=0,
        copy=False,
        tracking=True,
    )

    # ─── Dokumen Persyaratan ─────────────────────────────────────────────────
    # Dokumen Umum
    doc_surat_permohonan = fields.Binary(
        string='Surat Permohonan Sertifikasi Halal',
        attachment=True,
    )
    doc_surat_permohonan_fname = fields.Char()

    doc_legalitas_usaha = fields.Binary(
        string='Dokumen Legalitas Usaha (NIB / SIUP / TDP)',
        attachment=True,
    )
    doc_legalitas_usaha_fname = fields.Char()

    doc_list_produk = fields.Binary(
        string='Daftar Produk & Bahan Baku',
        attachment=True,
    )
    doc_list_produk_fname = fields.Char()

    doc_proses_produksi = fields.Binary(
        string='Diagram Alur Proses Produksi',
        attachment=True,
    )
    doc_proses_produksi_fname = fields.Char()

    doc_manual_shms = fields.Binary(
        string='Manual Sistem Jaminan Halal (SJH / SHMS)',
        attachment=True,
    )
    doc_manual_shms_fname = fields.Char()

    # Dokumen Tambahan (Import)
    doc_halal_cert_asal = fields.Binary(
        string='Sertifikat Halal Negara Asal (Import)',
        attachment=True,
    )
    doc_halal_cert_asal_fname = fields.Char()

    doc_hasil_audit = fields.Binary(
        string='Laporan Hasil Audit Halal',
        attachment=True,
    )
    doc_hasil_audit_fname = fields.Char()

    # Sertifikat Final
    doc_sertifikat_halal = fields.Binary(
        string='Sertifikat Halal (Final)',
        attachment=True,
        copy=False,
    )
    doc_sertifikat_halal_fname = fields.Char()

    # ─── Lini Produk Halal ───────────────────────────────────────────────────
    lini_produk_ids = fields.One2many(
        comodel_name='halal.registrasi.line',
        inverse_name='halal_id',
        string='Lini Produk',
    )

    # ─── Perpanjangan ────────────────────────────────────────────────────────
    is_renewal = fields.Boolean(
        string='Perpanjangan Sertifikat',
        default=False,
        tracking=True,
    )
    parent_halal_id = fields.Many2one(
        comodel_name='halal.registrasi',
        string='Sertifikat Sebelumnya',
        copy=False,
    )
    renewal_ids = fields.One2many(
        comodel_name='halal.registrasi',
        inverse_name='parent_halal_id',
        string='Riwayat Perpanjangan',
    )

    # ────────────────────────────────────────────────────────────────────────
    # Computed
    # ────────────────────────────────────────────────────────────────────────

    @api.depends('tanggal_expired')
    def _compute_is_expired(self):
        today = fields.Date.today()
        for rec in self:
            if rec.tanggal_expired:
                delta = (rec.tanggal_expired - today).days
                rec.sisa_hari = delta
                rec.is_expired = delta < 0
            else:
                rec.sisa_hari = 0
                rec.is_expired = False

    @api.onchange('client_id')
    def _onchange_client_id(self):
        self.mou_id = False
        return {
            'domain': {
                'mou_id': [
                    ('state', '=', 'mou'),
                    ('nama_cust', '=', self.client_id.id)
                ]
            }
        }

    @api.onchange('mou_id')
    def _onchange_mou_id(self):
        if self.mou_id:
            self.client_id = self.mou_id.nama_cust
            self.brand_name = self.mou_id.brand

            # Coba ambil dari line pertama dulu
            first_line = self.mou_id.maklon_line_ids[:1]
            if first_line and first_line.product:
                self.product_name = first_line.product.name
                if first_line.jenis_product:
                    self.halal_type = first_line.jenis_product
            else:
                # Fallback: kosongkan agar user isi manual
                self.product_name = False
        else:
            self.brand_name = False
            self.product_name = False

    # ────────────────────────────────────────────────────────────────────────
    # ORM Override
    # ────────────────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Baru')) == _('Baru'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'halal.registrasi'
                ) or _('Baru')
        return super().create(vals_list)

    def copy(self, default=None):
        default = dict(default or {})
        default['name'] = _('Baru')
        default['state'] = 'draft'
        default['revision_counter'] = 0
        default['nomor_sertifikat'] = False
        default['doc_sertifikat_halal'] = False
        return super().copy(default)

    # ────────────────────────────────────────────────────────────────────────
    # Validasi
    # ────────────────────────────────────────────────────────────────────────

    @api.constrains('lembaga_sertifikasi', 'lembaga_luar_negeri')
    def _check_lembaga_luar_negeri(self):
        for rec in self:
            if rec.lembaga_sertifikasi == 'luar_negeri' and not rec.lembaga_luar_negeri:
                raise ValidationError(
                    _('Nama lembaga sertifikasi luar negeri wajib diisi.')
                )

    @api.constrains('tanggal_terbit', 'tanggal_expired')
    def _check_tanggal_sertifikat(self):
        for rec in self:
            if rec.tanggal_terbit and rec.tanggal_expired:
                if rec.tanggal_expired <= rec.tanggal_terbit:
                    raise ValidationError(
                        _('Tanggal kadaluarsa harus lebih besar dari tanggal terbit.')
                    )

    def _cek_dokumen_wajib(self):
        """Validasi kelengkapan dokumen wajib sebelum pengajuan."""
        self.ensure_one()
        kurang = []
        if not self.doc_surat_permohonan:
            kurang.append(_('Surat Permohonan Sertifikasi Halal'))
        if not self.doc_legalitas_usaha:
            kurang.append(_('Dokumen Legalitas Usaha'))
        if not self.doc_list_produk:
            kurang.append(_('Daftar Produk & Bahan Baku'))
        if not self.doc_proses_produksi:
            kurang.append(_('Diagram Alur Proses Produksi'))
        if not self.doc_manual_shms:
            kurang.append(_('Manual SJH / SHMS'))
        if self.halal_type == 'import' and not self.doc_halal_cert_asal:
            kurang.append(_('Sertifikat Halal Negara Asal (wajib untuk produk import)'))
        if not self.lini_produk_ids:
            kurang.append(_('Minimal satu lini produk harus diisi'))
        return kurang

    # ────────────────────────────────────────────────────────────────────────
    # Transisi State
    # ────────────────────────────────────────────────────────────────────────

    def action_ajukan_dokumen(self):
        """Draft → Pengajuan Dokumen: validasi dokumen wajib."""
        for rec in self:
            kurang = rec._cek_dokumen_wajib()
            if kurang:
                raise UserError(
                    _('Dokumen berikut wajib diunggah sebelum pengajuan:\n- %s')
                    % '\n- '.join(kurang)
                )
            today = fields.Date.today()
            rec.write({
                'state': 'pengajuan',
                'tanggal_pengajuan': today,
                'target_selesai': today + timedelta(days=rec.sla_hari or 30),
            })
            rec.message_post(
                body=_('Dokumen diajukan. Target selesai: %s')
                % (today + timedelta(days=rec.sla_hari or 30)).strftime('%d %B %Y'),
                message_type='notification',
            )
        return True

    def action_verifikasi_internal(self):
        """Pengajuan → Verifikasi Internal oleh Regulatory."""
        for rec in self:
            rec.write({
                'state': 'verifikasi_internal',
                'disetujui_regulatory': self.env.uid,
                'tanggal_verifikasi': fields.Datetime.now(),
            })
            rec.message_post(
                body=_('Verifikasi internal dilakukan oleh %s.') % self.env.user.name,
                message_type='notification',
            )
        return True

    def action_submit_ke_lembaga(self):
        """Verifikasi Internal → Diajukan ke Lembaga."""
        for rec in self:
            if not rec.disetujui_regulatory:
                raise UserError(
                    _('Verifikasi internal harus diselesaikan sebelum mengajukan ke lembaga.')
                )
            rec.write({'state': 'submitted_lembaga'})
            rec.message_post(
                body=_('Berkas resmi diajukan ke %s.')
                % dict(rec._fields['lembaga_sertifikasi'].selection).get(
                    rec.lembaga_sertifikasi, ''
                ),
                message_type='notification',
            )
        return True

    def action_audit_halal(self):
        """Diajukan ke Lembaga → Audit Halal (lembaga melakukan audit)."""
        for rec in self:
            rec.write({'state': 'audit_halal'})
            rec.message_post(
                body=_('Proses audit halal oleh lembaga sedang berlangsung.'),
                message_type='notification',
            )
        return True

    def action_menunggu_keputusan(self):
        """Audit Halal → Menunggu Keputusan."""
        for rec in self:
            if not rec.doc_hasil_audit:
                raise UserError(
                    _('Unggah laporan hasil audit halal sebelum melanjutkan.')
                )
            rec.write({'state': 'menunggu_keputusan'})
            rec.message_post(
                body=_('Audit selesai. Menunggu keputusan dari lembaga sertifikasi.'),
                message_type='notification',
            )
        return True

    def action_terbitkan_sertifikat(self):
        """Menunggu Keputusan → Sertifikat Terbit."""
        for rec in self:
            if not rec.nomor_sertifikat:
                raise UserError(_('Nomor sertifikat halal wajib diisi.'))
            if not rec.tanggal_terbit:
                raise UserError(_('Tanggal terbit sertifikat wajib diisi.'))
            if not rec.tanggal_expired:
                raise UserError(_('Tanggal kadaluarsa sertifikat wajib diisi.'))
            if not rec.doc_sertifikat_halal:
                raise UserError(
                    _('Unggah file sertifikat halal final sebelum menerbitkan.')
                )
            rec.write({'state': 'sertifikat_terbit'})
            # Sinkronisasi ke registrasi.produk jika tertaut
            if rec.produk_id:
                rec.produk_id.write({
                    'halal_cert_attachment': rec.doc_sertifikat_halal,
                    'halal_type': rec.halal_type,
                })
            rec.message_post(
                body=_('✅ Sertifikat Halal berhasil diterbitkan! No: %s. '
                       'Berlaku hingga: %s.')
                % (rec.nomor_sertifikat,
                   rec.tanggal_expired.strftime('%d %B %Y')),
                message_type='notification',
                subtype_xmlid='mail.mt_comment',
            )
        return True

    def action_tolak(self):
        """Tolak / kembalikan untuk revisi."""
        for rec in self:
            if not rec.catatan_penolakan:
                raise UserError(
                    _('Isi catatan penolakan / alasan revisi sebelum menolak.')
                )
            new_counter = rec.revision_counter + 1
            rec.write({
                'state': 'ditolak',
                'revision_counter': new_counter,
            })
            rec.message_post(
                body=_('❌ Ditolak (revisi ke-%d). Alasan:\n%s')
                % (new_counter, rec.catatan_penolakan),
                message_type='notification',
                subtype_xmlid='mail.mt_comment',
            )
        return True

    def action_reset_ke_draft(self):
        """Reset ke Draft untuk perbaikan dokumen."""
        for rec in self:
            rec.write({
                'state': 'draft',
                'catatan_penolakan': False,
            })
            rec.message_post(
                body=_('Record direset ke Draft untuk perbaikan.'),
                message_type='notification',
            )
        return True

    def action_tandai_kadaluarsa(self):
        """Tandai sertifikat sebagai kadaluarsa (manual / otomatis)."""
        for rec in self:
            rec.write({'state': 'kadaluarsa'})
            rec.message_post(
                body=_('⚠️ Sertifikat halal telah kadaluarsa.'),
                message_type='notification',
                subtype_xmlid='mail.mt_comment',
            )
        return True

    def action_buat_perpanjangan(self):
        """Buat record perpanjangan sertifikat baru berdasarkan yang sudah ada."""
        self.ensure_one()
        new_rec = self.copy({
            'is_renewal': True,
            'parent_halal_id': self.id,
            'product_name': self.product_name,
            'client_id': self.client_id.id,
            'halal_type': self.halal_type,
            'jenis_produk': self.jenis_produk,
            'lembaga_sertifikasi': self.lembaga_sertifikasi,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Perpanjangan Sertifikat Halal'),
            'res_model': 'halal.registrasi',
            'res_id': new_rec.id,
            'view_mode': 'form',
        }

    # ────────────────────────────────────────────────────────────────────────
    # Scheduled Action: auto-mark expired
    # ────────────────────────────────────────────────────────────────────────

    @api.model
    def _cron_tandai_kadaluarsa(self):
        """Scheduled action: otomatis tandai sertifikat yang sudah kadaluarsa."""
        today = fields.Date.today()
        expired_recs = self.search([
            ('state', '=', 'sertifikat_terbit'),
            ('tanggal_expired', '<', today),
        ])
        for rec in expired_recs:
            rec.action_tandai_kadaluarsa()