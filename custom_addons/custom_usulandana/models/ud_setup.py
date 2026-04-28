from odoo import models,fields,api


class UsulanDanaSetup(models.Model):
    _name = 'usulan.dana.setup'
    _description = 'Setup Item Usulan Dana'

    date_created = fields.Datetime(string='Tgl Dibuat', default=fields.Datetime.now, readonly=True)
    user_id = fields.Many2one('res.users', string='Akun Pembuat', default=lambda self: self.env.user, readonly=True)
    name = fields.Char(string='Nama Item', required=True)
    account_id = fields.Many2one('account.account', string='COA')
    asset_type = fields.Selection([
        ('fixed', 'Fixed Asset'),
        ('current', 'Current Asset')
    ], string='Kategori Asset')
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