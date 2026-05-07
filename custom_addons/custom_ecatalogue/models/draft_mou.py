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
    # kode draft mou : MIK-tahun/bulan/DM - 0001 - Draft
    # kode E-mou : MIK-tahun/bulan/MOU - 0001
    # kode PR : MIK-tahun/bulan/PO - 0001

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('draft_name', 'New') == 'New':
                vals['draft_name'] = self.env['ir.sequence'].next_by_code('draft.mou.sequence') or 'New'
        return super().create(vals_list)

    def action_confirm_mou(self):
        for rec in self:
            if rec.draft_name and 'DM' in rec.draft_name:
                rec.draft_name = rec.draft_name.replace('DM', 'MOU')
            rec.state = 'mou'

    def action_draft(self):
        for rec in self:
            if rec.draft_name and 'MOU' in rec.draft_name:
                rec.draft_name = rec.draft_name.replace('MOU', 'DM')
            rec.state = 'draft'

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
            ('type_tax_use', '=', 'purchase'),
            ('name', 'ilike', '11%'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)

        for line in self:
            if line.draft_id.is_ppn:
                if tax_11:
                    line.tax_ids = [(6, 0, tax_11.ids)]
                else:
                    from odoo import exceptions
                    raise exceptions.UserError(
                        "Pajak dengan nama mengandung '11%' untuk Penjualan tidak ditemukan di master data Accounting!"
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