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
    #  ATTACHMENT (hanya file design, form final ada di approval)
    # ─────────────────────────────────────────────
    attachment_design = fields.Binary(string='File Design', attachment=True)
    attachment_design_fname = fields.Char(string='Nama File Design')

    # ─────────────────────────────────────────────
    #  LINK KE APPROVAL
    # ─────────────────────────────────────────────
    approval_id = fields.Many2one(
        'design.approval',
        string='Approval',
        copy=False,
        readonly=True,
    )

    # ─────────────────────────────────────────────
    #  STATE
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
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('design.usulan')
                    or _('New')
                )
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
        """On Progress → buat design.approval → state approval_marketing"""
        for rec in self:
            if not rec.product_line_ids:
                raise UserError(_('Harap isi minimal satu produk sebelum mengajukan approval.'))

            # Cek apakah sudah ada approval aktif
            existing = self.env['design.approval'].search([
                ('usulan_id', '=', rec.id),
                ('state', 'not in', ['done', 'reject']),
            ], limit=1)

            if not existing:
                approval = self.env['design.approval'].create({
                    'usulan_id': rec.id,
                    'date': fields.Date.context_today(rec),
                    'state': 'approval_marketing',
                })
                rec.approval_id = approval.id

            rec.state = 'approval_marketing'
            rec.message_post(body=_('Diajukan ke Approval Manager Marketing.'))

    def action_revisi_design(self):
        """Revisi — catat riwayat, reset state ke On Progress."""
        STATE_LABEL = dict(self._fields['state'].selection)
        for rec in self:
            rec.revisi_count += 1
            state_from = STATE_LABEL.get(rec.state, rec.state)
            self.env['design.revisi.line'].create({
                'usulan_id': rec.id,
                'revisi_ke': rec.revisi_count,
                'tanggal': fields.Datetime.now(),
                'user_id': self.env.user.id,
                'state_from': state_from,
            })
            rec.write({
                'state': 'progress',
                'approval_id': False,
            })
            rec.message_post(body=_(
                '🔄 Revisi ke-%d dimulai (dari: %s). Status kembali ke On Progress.'
            ) % (rec.revisi_count, state_from))

    def action_open_approval(self):
        """Buka record approval terkait."""
        self.ensure_one()
        if not self.approval_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': 'Approval Design',
            'res_model': 'design.approval', 
            'view_mode': 'form',
            'res_id': self.approval_id.id,
            'target': 'current',
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