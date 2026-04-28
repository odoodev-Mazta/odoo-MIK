from odoo import models,fields,api

class UsulanUpCountry(models.Model):
    _name = 'usulan.up.country'
    _description = 'Usulan Up Country'
    _inherit = ['mail.activity.mixin', 'mail.thread']
    _order = 'date_created desc'

    name = fields.Char(string="No Usulan", readonly=True, copy=False, default='New')
    date_created = fields.Datetime(string='Tgl Dibuat', default=fields.Datetime.now, readonly=True)
    date_submitted = fields.Datetime(string='Tgl Diajukan', readonly=True)
    department_id = fields.Many2one('hr.department', string="Departemen", readonly=False)
    tujuan = fields.Char(string='Tujuan', required=True, tracking=True)
    tipe = fields.Selection([
        ('operasional', 'Operasional'),
        ('proyek', 'Proyek'),
        ('darurat', 'Darurat/Urgent')
    ], string='Tipe Usulan', required=True)
    employee_id = fields.Many2one('hr.employee', string='PIC (Karyawan)', readonly=False)
    phone_id = fields.Char(string="No WA PIC", readonly=False)
    vendor_id = fields.Many2one('res.partner', string="Vendor")
    vendor_phone = fields.Char(string="No WA")
    payment_method = fields.Selection([
        ('transfer', 'Transfer Bank'),
        ('cash', 'Tunai'),
        ('cheque', 'Cek/Giro')
    ], string='Metode Payment')
    rekening_vendor_id = fields.Char(string="Data Rekening")
    alamat_vendor_id = fields.Char(string="Alamat")
    amount = fields.Monetary(string='Nilai Usulan', currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('to_approve', 'Menunggu Approval'),
        ('approve', 'Approved'),
        ('reject', 'Ditolak'),
        ('rilis', 'Rilis'),
        ('cancel', 'Cancel')
    ], string='Status Utama', default='draft', tracking=True)
    jenis = fields.Selection([
        ('draft', 'Draft'),
        ('usulan_dana', 'Usulan Dana')
    ], string='Jenis', compute='_compute_kolom_list_view', store=True)
    status_approval = fields.Selection([
        ('waiting', 'Menunggu'),
        ('approved', 'Approved'),
        ('rejected', 'Ditolak')
    ], string='Status Approval', compute='_compute_kolom_list_view', store=True)
    status_payment = fields.Selection([
        ('unpaid', 'Belum Rilis'),
        ('rilis', 'Sudah Rilis')
    ], string='Status Payment', compute='_compute_kolom_list_view', store=True)

    @api.depends('state')
    def _compute_kolom_list_view(self):
        """ Mengisi otomatis Jenis, Status Approval, dan Status Payment berdasarkan state utama """
        for record in self:
            # Logic Jenis
            record.jenis = 'draft' if record.state == 'draft' else 'usulan_dana'

            if record.state == 'to_approve':
                record.status_approval = 'waiting'
            elif record.state in ('approve', 'rilis'):
                record.status_approval = 'approved'
            elif record.state == 'reject':
                record.status_approval = 'rejected'
            else:
                record.status_approval = False

            record.status_payment = 'rilis' if record.state == 'rilis' else 'unpaid'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('usulan.up.country') or 'New'
        return super().create(vals_list)

        return super().create(vals_list)

    def action_submit(self):
        for record in self:
            record.state = 'to_approve'
            record.date_submitted = fields.Datetime.now()

    def action_approve(self):
        for record in self:
            record.state = 'approve'

    def action_reject(self):
        for record in self:
            record.state = 'reject'

    def action_rilis(self):
        for record in self:
            record.state = 'rilis'

    def action_cancel(self):
        for record in self:
            record.state = 'cancel'