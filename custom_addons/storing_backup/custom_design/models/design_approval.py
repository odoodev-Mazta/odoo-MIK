from odoo import models, fields, api, _
from odoo.exceptions import UserError


class DesignApproval(models.Model):
    _name = 'design.approval'
    _description = 'Approval Design'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    # ─────────────────────────────────────────────
    #  IDENTITAS
    # ─────────────────────────────────────────────
    name = fields.Char(
        string='No. Approval',
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    date = fields.Date(
        string='Tgl. Pengajuan',
        default=fields.Date.context_today,
        readonly=True,
    )

    # ─────────────────────────────────────────────
    #  LINK KE USULAN
    # ─────────────────────────────────────────────
    usulan_id = fields.Many2one(
        'design.usulan',
        string='No. Design',
        readonly=True,
        ondelete='cascade',
        tracking=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Pelanggan',
        related='usulan_id.partner_id',
        store=True,
        readonly=True,
    )
    mou_id = fields.Many2one(
        'draft.maklon',
        string='No. MOU',
        related='usulan_id.mou_id',
        store=True,
        readonly=True,
    )
    brand = fields.Char(
        string='Brand',
        related='usulan_id.brand',
        store=True,
        readonly=True,
    )
    product_line_ids = fields.One2many(
        related='usulan_id.product_line_ids',
        readonly=True,
    )
    attachment_design = fields.Binary(
        related='usulan_id.attachment_design',
        readonly=True,
    )
    attachment_design_fname = fields.Char(
        related='usulan_id.attachment_design_fname',
        readonly=True,
    )

    # ─────────────────────────────────────────────
    #  STATE APPROVAL
    # ─────────────────────────────────────────────
    state = fields.Selection([
        ('approval_marketing',  'Approval Manager Marketing'),
        ('approval_client',     'Approval Client'),
        ('approval_ro',         'Approval RO'),
        ('upload_form',         'Upload Form Design'),
        ('done',                'Done'),
        ('reject',              'Rejected'),
    ], string='Status', default='approval_marketing',
       tracking=True, copy=False)

    # ─────────────────────────────────────────────
    #  APPROVAL FIELDS
    # ─────────────────────────────────────────────
    approved_by_marketing = fields.Many2one(
        'res.users', string='Disetujui Marketing',
        readonly=True, copy=False,
    )
    approved_by_marketing_date = fields.Datetime(
        string='Tgl Approve Marketing',
        readonly=True, copy=False,
    )
    approved_by_client = fields.Many2one(
        'res.users', string='Disetujui Client',
        readonly=True, copy=False,
    )
    approved_by_client_date = fields.Datetime(
        string='Tgl Approve Client',
        readonly=True, copy=False,
    )
    approved_by_ro = fields.Many2one(
        'res.users', string='Disetujui RO',
        readonly=True, copy=False,
    )
    approved_by_ro_date = fields.Datetime(
        string='Tgl Approve RO',
        readonly=True, copy=False,
    )

    # ─────────────────────────────────────────────
    #  REJECT FIELDS
    # ─────────────────────────────────────────────
    reject_reason = fields.Text(
        string='Alasan Reject',
        readonly=True, copy=False,
    )
    rejected_by = fields.Many2one(
        'res.users', string='Ditolak oleh',
        readonly=True, copy=False,
    )
    rejected_date = fields.Datetime(
        string='Tgl Reject',
        readonly=True, copy=False,
    )

    # ─────────────────────────────────────────────
    #  UPLOAD FORM FINAL
    # ─────────────────────────────────────────────
    attachment_form = fields.Binary(
        string='Form Design Final',
        attachment=True,
    )
    attachment_form_fname = fields.Char(
        string='Nama File Form Design',
    )

    revisi_count = fields.Integer(
        related='usulan_id.revisi_count',
        string='Jumlah Revisi',
        readonly=True,
    )

    # ─────────────────────────────────────────────
    #  SEQUENCE
    # ─────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('design.approval')
                    or _('New')
                )
        return super().create(vals_list)

    # ─────────────────────────────────────────────
    #  STATE MACHINE
    # ─────────────────────────────────────────────
    def action_approve_marketing(self):
        for rec in self:
            rec.write({
                'approved_by_marketing': self.env.user.id,
                'approved_by_marketing_date': fields.Datetime.now(),
                'state': 'approval_client',
            })
            # sync state ke usulan
            rec.usulan_id.write({'state': 'approval_client'})
            rec.message_post(
                body=_('✅ Disetujui Manager Marketing. Menunggu Approval Client.')
            )

    def action_approve_client(self):
        for rec in self:
            rec.write({
                'approved_by_client': self.env.user.id,
                'approved_by_client_date': fields.Datetime.now(),
                'state': 'approval_ro',
            })
            rec.usulan_id.write({'state': 'approval_ro'})
            rec.message_post(
                body=_('✅ Disetujui Client. Menunggu Approval RO.')
            )

    def action_approve_ro(self):
        for rec in self:
            rec.write({
                'approved_by_ro': self.env.user.id,
                'approved_by_ro_date': fields.Datetime.now(),
                'state': 'upload_form',
            })
            rec.usulan_id.write({'state': 'upload_form'})
            rec.message_post(
                body=_('✅ Disetujui RO. Menunggu upload Form Design Final.')
            )

    def action_upload_done(self):
        for rec in self:
            if not rec.attachment_form:
                raise UserError(_('Harap upload File Form Design Final terlebih dahulu.'))
            rec.write({
                'state': 'done',
            })
            rec.usulan_id.write({
                'state': 'done',
                'date_done': fields.Date.context_today(rec),
                'attachment_form': rec.attachment_form,
                'attachment_form_fname': rec.attachment_form_fname,
            })
            rec.message_post(
                body=_('✅ Form Design Final diupload. Status: Done.')
            )

    def action_revisi(self):
        """Reset approval, kembalikan usulan ke On Progress, hapus record approval ini."""
        for rec in self:
            usulan = rec.usulan_id
            usulan.action_revisi_design()
            rec.message_post(
                body=_('🔄 Revisi diminta dari Approval. Usulan dikembalikan ke On Progress.')
            )
            # Hapus record approval — akan dibuat ulang saat diajukan lagi
            rec.unlink()

    def action_reject(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Alasan Penolakan'),
            'res_model': 'design.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_approval_id': self.id,
                'default_usulan_id': self.usulan_id.id,
            },
        }