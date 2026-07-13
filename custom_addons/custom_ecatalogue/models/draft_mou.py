from odoo import models, fields, api, exceptions


class DraftMaklon(models.Model):
    _name = 'draft.maklon'
    _rec_name = 'draft_name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Draft Maklon'

    nama_cust = fields.Many2one('res.partner', string="Nama Pelanggan", tracking=True)
    alamat_cust = fields.Char(string="Alamat")
    ktp_cust = fields.Char(string="No. KTP")
    foto_ktp_cust = fields.Binary(string="KTP")
    npwp_cust = fields.Char(string="NPWP")
    foto_npwp_cust = fields.Binary(string="Foto NPWP")
    email_cust = fields.Char(string="Email")
    telp_cust = fields.Char(string="Telp")
    jabatan_cust = fields.Char(string="Jabatan", store=True)
    brand = fields.Char(string="Nama Brand")

    currency_id = fields.Many2one("res.currency", string="Currency",
                                  default=lambda self: self.env.company.currency_id.id)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('mou', 'MOU')
    ], string="Status", default='draft', tracking=True)
    draft_name = fields.Char(string="Kode MOU", copy=False, default="New")
    tgl_draft = fields.Date(string="Tgl Draft", default=fields.Datetime.now)
    tgl_start = fields.Date(string="Tgl Start")
    tgl_end = fields.Date(string="Tgl End")
    origin_draft_id = fields.Many2one('draft.maklon', string='Berasal dari Draft', readonly=True)

    maklon_line_ids = fields.One2many('draft.maklon.line', 'draft_id', string="Detail Produk & Tahapan")
    is_ppn = fields.Boolean(string='PPN 11%', default=False, tracking=True)

    nilai_kontrak = fields.Monetary (
        string='Total Nilai Kontrak',
        currency_field='currency_id',
        compute='_compute_nilai_kontrak',
        store=True,
    )

    @api.onchange('nama_cust')
    def _onchange_nama_cust(self):
        if self.nama_cust:
            self.alamat_cust = self.nama_cust.contact_address or ''
            self.email_cust = self.nama_cust.email or ''
            self.telp_cust = self.nama_cust.phone or self.nama_cust.mobile or ''
            self.jabatan_cust = self.nama_cust.function or ''
        else:
            self.alamat_cust = False
            self.email_cust = False
            self.telp_cust = False
            self.jabatan_cust = False

    def action_confirm_mou(self):
        for rec in self:
            if rec.draft_name and 'DM' in rec.draft_name:
                rec.draft_name = rec.draft_name.replace('DM', 'MOU')
            rec.state = 'mou'
            rec._sync_master_brand()

    def action_draft(self):
        for rec in self:
            if rec.draft_name and 'MOU' in rec.draft_name:
                rec.draft_name = rec.draft_name.replace('MOU', 'DM')
            rec.state = 'draft'

    def _sync_master_brand(self):
        for rec in self:
            if not rec.nama_cust or not rec.brand:
                continue
            master = self.env['master.data.brand'].search([
                ('partner_id', '=', rec.nama_cust.id)
            ], limit=1)
            if not master:
                master = self.env['master.data.brand'].create({
                    'partner_id': rec.nama_cust.id,
                })
            exist = self.env['master.data.brand.line'].search([
                ('master_brand_id', '=', master.id),
                ('brand', '=', rec.brand),
            ], limit=1)
            if not exist:
                self.env['master.data.brand.line'].create({
                    'master_brand_id': master.id,
                    'brand': rec.brand,
                })

    # ────────────────────────────────────────────────────────────────────
    # REPEAT ORDER
    # ────────────────────────────────────────────────────────────────────

    def action_repeat_order(self):
        """
        Repeat Order untuk MOU yang sama (self):
        1. Pastikan stage 'MOU' & 'Biaya Registrasi' tertandai Selesai di
           dashboard tracking (registrasi/design TIDAK dipaksa — statusnya
           mengikuti kondisi approval BPOM/Halal yang sebenarnya).
        2. Buat Sales Order baru, order_line auto-parsing dari
           maklon_line_ids: Produk, Qty, Unit, Unit Price (HNA), Amount.
        3. Tandai SO tersebut sebagai Repeat Order.
        """
        self.ensure_one()
        if self.state != 'mou':
            raise exceptions.UserError(('MOU harus berstatus Confirmed sebelum bisa di-repeat.'))
        if not self.maklon_line_ids:
            raise exceptions.UserError(('Tidak ada data produk di MOU ini untuk di-repeat.'))

        self._ensure_biaya_registrasi_done()

        new_so = self._create_repeat_sale_order()

        self.message_post(
            body=('Repeat Order dibuat: Sales Order %s.') % new_so.name
        )

        return {
            'type': 'ir.actions.act_window',
            'name': ('Repeat Order - Sales Order'),
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': new_so.id,
        }

    def _ensure_biaya_registrasi_done(self):
        """Pastikan mou.setup stage Biaya Registrasi tertandai lunas."""
        self.ensure_one()
        setup = self.env['mou.setup'].search([
            ('mou_id', '=', self.id),
            ('state', '=', 'biaya_registrasi'),
        ], limit=1)

        if setup and (setup.reg_payment_date or setup.is_free):
            return  # sudah lunas, tidak perlu diubah

        if not setup:
            setup = self.env['mou.setup'].create({
                'name': ('REPEAT/REG/%s') % self.draft_name,
                'mou_id': self.id,
                'state': 'biaya_registrasi',
                'date': fields.Date.today(),
                'keterangan': ('Repeat Order — Biaya Registrasi ditandai selesai otomatis'),
            })

        # Menandai lunas via is_free -> otomatis trigger _auto_create_registrasi_and_design()
        # kalau brand/design belum pernah dibuat untuk mou_id ini.
        setup.write({'is_free': True})

    def _create_repeat_sale_order(self):
        """Buat SO baru, order_line auto-parsing dari maklon_line_ids."""
        self.ensure_one()

        tax_11 = False
        if self.is_ppn:
            tax_11 = self.env['account.tax'].search([
                ('amount', '=', 11),
                ('amount_type', '=', 'percent'),
                ('type_tax_use', '=', 'sale'),
                ('active', '=', True),
            ], limit=1)

        order_lines = []
        for line in self.maklon_line_ids:
            harga_setelah_diskon = line.product_hna * (1 - (line.diskon or 0.0) / 100.0)
            order_lines.append((0, 0, {
                'product_id': line.product.id,
                'product_uom_qty': line.product_qty or 1.0,
                'product_uom_id': line.uom_id.id if line.uom_id else False,  # ← FIX: product_uom_id
                'price_unit': harga_setelah_diskon,
                'name': f"{line.product.display_name} - Repeat Order",
                'tax_ids': [(6, 0, tax_11.ids)] if tax_11 else [(5, 0, 0)],
            }))

        return self.env['sale.order'].create({
            'partner_id': self.nama_cust.id,
            'mou_id': self.id,
            'timeline_stage': 'dp',
            'is_repeat_order': True,
            'order_line': order_lines,
        })

    @api.depends('maklon_line_ids.total_value')
    def _compute_nilai_kontrak(self):
        for rec in self :
            rec.nilai_kontrak = sum(rec.maklon_line_ids.mapped('total_value'))
    # kode draft mou : MIK-tahun/bulan/DM - 0001 - Draft
    # kode E-mou : MIK-tahun/bulan/MOU - 0001
    # kode PR : MIK-tahun/bulan/PO - 0001

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('draft_name', 'New') == 'New':
                vals['draft_name'] = self.env['ir.sequence'].next_by_code('draft.mou.sequence') or 'New'
        return super().create(vals_list)

    # def _sync_master_brand(self):
    #     for rec in self:
    #         if not rec.nama_cust or not rec.brand:
    #             continue

    #         master = self.env['master.data.brand'].search([
    #             ('partner_id', '=', rec.nama_cust.id)
    #         ], limit=1)

    #         if not master:
    #             master = self.env['master.data.brand'].create({
    #                 'partner_id': rec.nama_cust.id,
    #             })

    #         exist = self.env['master.data.brand.line'].search([
    #             ('master_brand_id', '=', master.id),
    #             ('brand', '=', rec.brand),
    #         ], limit=1)

    #         if not exist:
    #             self.env['master.data.brand.line'].create({
    #                 'master_brand_id': master.id,
    #                 'brand': rec.brand,
    #             })

class DraftMaklonLine(models.Model):
    _name = 'draft.maklon.line'
    _description = 'Draft Maklon Line'

    draft_id = fields.Many2one('draft.maklon', string="Draft Ref", ondelete='cascade')

    currency_id = fields.Many2one(related='draft_id.currency_id', store=True)

    tahap = fields.Selection([
        ('1x_tahap', '1x'),
        ('2x_tahap', '2x'),
        ('3x_tahap', '3x'),
        ('4x_tahap', '4x'),
        ('5x_tahap', '5x'),
    ], string="Tahap")

    product = fields.Many2one('product.product', string="Product", required=True)
    jenis_product = fields.Selection([('lokal', 'Lokal'), ('import', 'Import')], string="Jenis Produk")
    date_estimasi = fields.Date(string="Estimasi Tanggal")

    kemasan = fields.Selection([
        ('jar', 'Jar'), ('tube', 'Tube'), ('sachet', 'Sachet'),
        ('botol', 'Botol'), ('pump', 'Tube Pump')
    ], string="Jenis Kemasan")
    ukuran = fields.Char(string="Ukuran Kemasan")
    uom_id = fields.Many2one('uom.uom', string="Satuan")

    product_qty = fields.Float(string="Quantity", default=1.0)
    product_hna = fields.Float(string="HNA(Rp)")
    diskon = fields.Float(string="Diskon (%)", default=0.0)

    tax_ids = fields.Many2many(
        'account.tax',
        string='Pajak',
        domain="[('type_tax_use', '=', 'purchase')]",
        compute='_compute_tax_ids',
        store=True,
        readonly=False
    )

    total_value = fields.Monetary(
        string="Total Value",
        compute='_compute_total_value',
        store=True,
        readonly=False
    )

    @api.depends('draft_id.is_ppn')
    def _compute_tax_ids(self):
        tax_11 = self.env['account.tax'].search([
            ('amount', '=', 11),
            ('amount_type', '=', 'percent'),
            ('type_tax_use', '=', 'sale'),
            ('active', '=', True),
        ], limit=1)
        for line in self:
            if line.draft_id.is_ppn:
                if tax_11:
                    line.tax_ids = [(6, 0, tax_11.ids)]
                else:
                    raise exceptions.UserError(
                        "Pajak PPN 11% tidak ditemukan! Pastikan sudah dikonfigurasi di Accounting."
                    )
            else:
                line.tax_ids = [(5, 0, 0)]

    @api.depends('product_qty', 'product_hna', 'diskon', 'tax_ids')
    def _compute_total_value(self):
        for rec in self:
            subtotal = rec.product_qty * rec.product_hna
            potongan_diskon = subtotal * (rec.diskon / 100.0)
            dpp = subtotal - potongan_diskon

            if rec.tax_ids:
                taxes = rec.tax_ids.compute_all(
                    dpp, rec.currency_id, 1.0,
                    product=rec.product,
                    partner=rec.draft_id.nama_cust
                )
                rec.total_value = taxes['total_included']
            else:
                rec.total_value = dpp