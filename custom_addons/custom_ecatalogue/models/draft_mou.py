from odoo import models,fields,api
from odoo.orm.decorators import readonly


class DraftMaklon(models.Model):
    _name = 'draft.maklon'
    _rec_name = 'draft_name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Draft Maklon'

    nama_cust = fields.Many2one('res.partner', string="Nama Pelanggan", readonly=False, tracking=True)
    alamat_cust = fields.Char(string="Alamat", readonly=False)
    ktp_cust = fields.Char(string="No. KTP", readonly=False)
    foto_ktp_cust = fields.Binary(string="KTP", readonly=False, required=False)
    npwp_cust = fields.Char(string="NPWP", readonly=False)
    foto_npwp_cust = fields.Binary(string="Foto NPWP", readonly=False)
    email_cust = fields.Char(string="Email", readonly=False)
    telp_cust = fields.Char(string="Telp", readonly=False)
    jabatan_cust = fields.Char(string="Jabatan", readonly=False, store=True)
    brand = fields.Char(string="Nama Brand", readonly=False)
    product = fields.Many2one('product.product', string="Product", readonly=False)
    jenis_product = fields.Selection([
        ('lokal','Lokal'),
        ('import','Import'),
    ], string="Jenis Produk", readonly=False)
    product_desc = fields.Text(string="Description", readonly=False)
    product_qty = fields.Float(string="Quantity", readonly=False)
    product_hna = fields.Float(string="HNA(Rp)", readonly=False)
    currency_id = fields.Many2one("res.currency", string="Currency",
                                  default=lambda self: self.env.company.currency_id.id)
    total_value = fields.Monetary(string="Total Value", readonly=False, currency_field='currency_id')
    ukuran = fields.Char(string="Ukuran Kemasan", readonly=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('mou', 'MOU')
    ], string="Status", default='draft', tracking=True)
    uom_id = fields.Many2one(
        'uom.uom',
        string="Satuan",
    )
    kemasan = fields.Selection([
        ('jar', 'Jar'),
        ('tube', 'Tube'),
        ('sachet', 'Sachet'),
        ('botol', 'Botol'),
        ('pump', 'Tube Pump'),
    ], string="Jenis Kemasan", readonly=False)
    stiker = fields.Selection([
        ('standard', 'Standard'),
        ('printing', 'Printing')
    ], string="Label/Stiker", readonly=False)
    draft_name = fields.Char(string="Kode MOU", readonly=False, copy=False, default="New")
    tgl_draft = fields.Date(string="Tgl Draft", readonly=False, default=fields.Datetime.now)
    tgl_start = fields.Date(string="Tgl Start", readonly=False)
    tgl_end = fields.Date(string="Tgl End", readonly=False)
    origin_draft_id = fields.Many2one('draft.maklon', string='Berasal dari Draft', readonly=True)
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