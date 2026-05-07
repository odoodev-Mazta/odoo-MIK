from odoo import models,fields,api


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
    ppn = fields.Float(string="PPN (%)", default=11.0)

    total_value = fields.Monetary(string="Total Value", compute='_compute_total_value', store=True)

    @api.depends('product_qty', 'product_hna', 'diskon', 'ppn')
    def _compute_total_value(self):
        for rec in self:
            subtotal = rec.product_qty * rec.product_hna
            potongan_diskon = subtotal * (rec.diskon / 100.0)
            harga_setelah_diskon = subtotal - potongan_diskon
            nilai_ppn = harga_setelah_diskon * (rec.ppn / 100.0)

            rec.total_value = harga_setelah_diskon + nilai_ppn