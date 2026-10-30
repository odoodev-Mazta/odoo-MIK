from odoo import models, fields, api, _
from odoo.exceptions import UserError


class DesignUsulan(models.Model):
    _name = 'design.usulan'
    _description = 'Usulan Design'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    # ─────────────────────────────────────────────
    #  IDENTITAS
    # ─────────────────────────────────────────────
    name = fields.Char(
        string='No. Design',
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    date = fields.Date(
        string='Tgl. Design',
        default=fields.Date.context_today,
        tracking=True,
    )
    date_done = fields.Date(string='Tgl. Done', tracking=True)

    # ─────────────────────────────────────────────
    #  PELANGGAN & MOU
    # ─────────────────────────────────────────────
    partner_id = fields.Many2one(
        'res.partner',
        string='Pelanggan',
        tracking=True,
        index=True,
        required=True,
    )
    mou_id = fields.Many2one(
        'draft.maklon',
        string='No. MOU',
        tracking=True,
        index=True,
        domain="[('state','=','mou'),('nama_cust','=',partner_id)]",
    )
    brand = fields.Char(string='Brand', tracking=True)

    # ─────────────────────────────────────────────
    #  NOTEBOOK – PRODUK
    # ─────────────────────────────────────────────
    product_line_ids = fields.One2many(
        'design.usulan.line',
        'usulan_id',
        string='Produk',
    )

    # ─────────────────────────────────────────────
    #  ATTACHMENT
    # ─────────────────────────────────────────────
    attachment_design = fields.Binary(string='File Design', attachment=True)
    attachment_design_fname = fields.Char(string='Nama File Design')

    attachment_form = fields.Binary(string='Form Design (Final)', attachment=True)
    attachment_form_fname = fields.Char(string='Nama File Form Design')

    # ─────────────────────────────────────────────
    #  STATE & APPROVAL FLAGS
    # ─────────────────────────────────────────────
    state = fields.Selection([
        ('draft',               'Draft'),
        ('progress',            'On Progress'),
        ('approval_marketing',  'Approval Manager Marketing'),
        ('approval_client',     'Approval Client'),
        ('approval_ro',         'Approval RO'),
        ('upload_form',         'Upload Form Design'),
        ('done',                'Done'),
        ('reject',              'Rejected'),
    ], string='Status', default='draft', tracking=True, copy=False)

    approved_by_marketing = fields.Many2one('res.users', string='Disetujui Marketing', readonly=True, copy=False)
    approved_by_marketing_date = fields.Datetime(string='Tgl Approve Marketing', readonly=True, copy=False)

    approved_by_client = fields.Many2one('res.users', string='Disetujui Client', readonly=True, copy=False)
    approved_by_client_date = fields.Datetime(string='Tgl Approve Client', readonly=True, copy=False)

    approved_by_ro = fields.Many2one('res.users', string='Disetujui RO', readonly=True, copy=False)
    approved_by_ro_date = fields.Datetime(string='Tgl Approve RO', readonly=True, copy=False)

    reject_reason = fields.Text(string='Alasan Reject', readonly=True, copy=False)
    rejected_by = fields.Many2one('res.users', string='Ditolak oleh', readonly=True, copy=False)
    rejected_date = fields.Datetime(string='Tgl Reject', readonly=True, copy=False)

    revisi_count = fields.Integer(string='Jumlah Revisi', default=0, copy=False)
    revisi_line_ids = fields.One2many(
        'design.revisi.line',
        'usulan_id',
        string='Riwayat Revisi',
    )

    is_ontime = fields.Boolean(string='Ontime', default=True)
    notes = fields.Text(string='Catatan')

    # ─────────────────────────────────────────────
    #  ONCHANGE
    # ─────────────────────────────────────────────
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        self.mou_id = False
        self.brand = False
        self.product_line_ids = [(5, 0, 0)]

    @api.onchange('mou_id')
    def _onchange_mou_id(self):
        if not self.mou_id:
            self.brand = False
            self.product_line_ids = [(5, 0, 0)]
            return

        mou = self.mou_id

        if hasattr(mou, 'brand') and mou.brand:
            self.brand = mou.brand
        elif hasattr(mou, 'nama_brand') and mou.nama_brand:
            self.brand = mou.nama_brand

        lines = []
        if hasattr(mou, 'maklon_line_ids') and mou.maklon_line_ids:
            for line in mou.maklon_line_ids:
                nama = False
                if hasattr(line, 'nama_produk') and line.nama_produk:
                    nama = line.nama_produk
                elif hasattr(line, 'product_id') and line.product_id:
                    nama = line.product_id.name
                if nama:
                    lines.append((0, 0, {'nama_produk': nama}))

        self.product_line_ids = [(5, 0, 0)] + lines

    # ─────────────────────────────────────────────
    #  SEQUENCE
    # ─────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('design.usulan') or _('New')
        return super().create(vals_list)

    # ─────────────────────────────────────────────
    #  STATE MACHINE
    # ─────────────────────────────────────────────
    def action_submit_form_design(self):
        """Draft → On Progress"""
        for rec in self:
            if not rec.mou_id:
                raise UserError(_('Harap pilih No. MOU terlebih dahulu.'))
            rec.state = 'progress'
            rec.message_post(body=_('Form design disubmit. Status: On Progress.'))

    def action_submit_to_approval(self):
        """On Progress → Approval Manager Marketing"""
        for rec in self:
            if not rec.product_line_ids:
                raise UserError(_('Harap isi minimal satu produk sebelum mengajukan approval.'))
            rec.state = 'approval_marketing'
            rec.message_post(body=_('Diajukan ke Approval Manager Marketing.'))

    def action_approve_marketing(self):
        """Approval Marketing → Approval Client"""
        for rec in self:
            rec.write({
                'approved_by_marketing': self.env.user.id,
                'approved_by_marketing_date': fields.Datetime.now(),
                'state': 'approval_client',
            })
            rec.message_post(body=_('✅ Disetujui oleh Manager Marketing. Menunggu Approval Client.'))

    def action_approve_client(self):
        """Approval Client → Approval RO"""
        for rec in self:
            rec.write({
                'approved_by_client': self.env.user.id,
                'approved_by_client_date': fields.Datetime.now(),
                'state': 'approval_ro',
            })
            rec.message_post(body=_('✅ Disetujui oleh Client. Menunggu Approval RO.'))

    def action_approve_ro(self):
        """Approval RO → Upload Form Design"""
        for rec in self:
            rec.write({
                'approved_by_ro': self.env.user.id,
                'approved_by_ro_date': fields.Datetime.now(),
                'state': 'upload_form',
            })
            rec.message_post(body=_(
                '✅ Disetujui oleh RO. Menunggu Manager Marketing upload Form Design Final.'
            ))

    def action_upload_done(self):
        """Upload Form Design → Done"""
        for rec in self:
            if not rec.attachment_form:
                raise UserError(_('Harap upload File Form Design terlebih dahulu.'))
            rec.write({
                'state': 'done',
                'date_done': fields.Date.context_today(rec),
            })
            rec.message_post(body=_('✅ Form Design final telah diupload. Status: Done.'))

    def action_revisi_design(self):
        """Revisi — catat ke revisi_line_ids, reset approval, balik ke On Progress."""
        STATE_LABEL = dict(self._fields['state'].selection)
        for rec in self:
            rec.revisi_count += 1
            state_from = STATE_LABEL.get(rec.state, rec.state)
            # Catat riwayat revisi
            self.env['design.revisi.line'].create({
                'usulan_id': rec.id,
                'revisi_ke': rec.revisi_count,
                'tanggal': fields.Datetime.now(),
                'user_id': self.env.user.id,
                'state_from': state_from,
            })
            rec.write({
                'state': 'progress',
                'approved_by_marketing': False,
                'approved_by_marketing_date': False,
                'approved_by_client': False,
                'approved_by_client_date': False,
                'approved_by_ro': False,
                'approved_by_ro_date': False,
                'reject_reason': False,
                'rejected_by': False,
                'rejected_date': False,
            })
            rec.message_post(body=_(
                '🔄 Revisi ke-%d dimulai (dari: %s). Status kembali ke On Progress.'
            ) % (rec.revisi_count, state_from))

    def action_reject(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Alasan Penolakan'),
            'res_model': 'design.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_usulan_id': self.id},
        }

    # ─────────────────────────────────────────────
    #  DASHBOARD DATA
    # ─────────────────────────────────────────────
    @api.model
    def get_dashboard_data(self):
        states = [
            'draft', 'progress', 'approval_marketing',
            'approval_client', 'approval_ro', 'upload_form', 'done', 'reject',
        ]
        counts = {s: self.search_count([('state', '=', s)]) for s in states}
        total = sum(counts.values())
        done = counts.get('done', 0)
        return {
            'total': total,
            'counts': counts,
            'done_pct': round(done / total * 100, 1) if total else 0,
        }
