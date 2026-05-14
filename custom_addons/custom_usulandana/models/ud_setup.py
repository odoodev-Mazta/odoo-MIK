from odoo import models,fields,api


class UsulanDanaSetup(models.Model):
    _name = 'usulan.dana.setup'
    _description = 'Setup Item Usulan Dana'

    date_created = fields.Datetime(string='Tgl Dibuat', default=fields.Datetime.now, readonly=True)
    user_id = fields.Many2one('res.users', string='Akun Pembuat', default=lambda self: self.env.user, readonly=True)
    name = fields.Char(string='Nama Item', required=True)
    account_id = fields.Many2one('account.account',
                                 string='COA',
                                 domain="[('is_header', '=', False)]")
    asset_type = fields.Selection([
        ('fixed', 'Fixed Asset'),
        ('current', 'Current Asset')
    ], string='Kategori Asset', compute='_compute_asset_type', readonly=True)
    state = fields.Selection([
        ('waiting', 'Menunggu Setup'),
        ('done', 'Valid')
    ], string='Status', compute='_compute_state', store=True)

    @api.depends('name', 'account_id')
    def _compute_state(self):
        for record in self:
            if record.name and record.account_id:
                record.state = 'done'
            else:
                record.state = 'waiting'

    @api.depends('account_id')
    def _compute_asset_type(self):
        for record in self:

            if not record.account_id:
                record.asset_type = False
                continue

            account_type = record.account_id.account_type

            if account_type == 'asset_fixed':
                record.asset_type = 'fixed'
            elif account_type == 'asset_current':
                record.asset_type = 'current'
            else:
                record.asset_type = False

class UsulanApprovalSetup(models.Model):
    _name = 'usulan.approval.setup'
    _description = 'Setup Matrix Approval Usulan'
    _order = 'min_amount asc'

    name = fields.Char(string='Nama Aturan', required=True, help="Misal: Usulan Kecil (< 5 Juta)")
    min_amount = fields.Float(string='Min.Nominal', required=True)
    max_amount = fields.Float(string='Max.Nominal', help="Kosongkan atau isi 0 jika tidak ada batas atas (unlimited)")

    # Checkbox siapa saja yang wajib approve
    need_head_dept = fields.Boolean(string='Need Head Dept', default=True)
    need_coo = fields.Boolean(string='Need COO', default=False)
    need_ceo = fields.Boolean(string='Need CEO', default=False)

class UsulanMasterKota(models.Model):
    _name = 'usulan.master.kota'
    _description = 'Master Data Kota Tujuan'
    _rec_name = 'name'
    _order = 'name asc'

    name = fields.Char(string='Nama Kota', required=True)
    category = fields.Selection([
        ('domestik', 'Dalam Negeri'),
        ('internasional', 'Luar Negeri'),
    ], string="Kategori", readonly=False)
    active = fields.Boolean(default=True)

class MasterJenisRencanaKerja(models.Model):
    _name = 'jenis.rencana.kerja'
    _description = 'Master Data Jenis Rencana Kerja'

    name = fields.Char(string="Jenis Rencana Kerja", readonly=False)
    active = fields.Boolean(default=True)

class MasterTipeVisit(models.Model):
    _name = 'tipe.visit'
    _description = 'Master Data Tipe Visit'

    name = fields.Char(string="Tipe Visit", readonly=False)
    active = fields.Boolean(default=True)

class MasterTujuanRencanaKerja(models.Model):
    _name = 'tujuan.rencana.kerja'
    _description = 'Master Data Tujuan Rencana Kerja'

    name = fields.Char(string="Rencana Kerja", readonly=False)
    active = fields.Boolean(default=True)

class MasterJenisTransportasi(models.Model):
    _name = 'jenis.transportasi'
    _description = 'Master Jenis Transportasi'

    name = fields.Char(string="Nama", readonly=False)
    active = fields.Boolean(default=True)