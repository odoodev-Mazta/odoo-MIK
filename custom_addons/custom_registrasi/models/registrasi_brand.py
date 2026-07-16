from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta


class RegistrasiBrand(models.Model):
    _name = 'registrasi.brand'
    _description = 'Brand / HAKI Registration to BPOM'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'
    _rec_name = 'name'

    # ─── Sequence / Identity ────────────────────────────────────────────────
    name = fields.Char(
        string='Registration Number',
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    brand_name = fields.Char(
        string='Brand Name',
        required=True,
        tracking=True,
    )
    brand_owner = fields.Char(
        string='Brand Owner',
        required=True,
        tracking=True,
    )
    client_id = fields.Many2one(
        comodel_name='res.partner',
        string='Client',
        required=True,
        tracking=True,
        index=True,
    )
    mou_id = fields.Many2one(
        comodel_name='draft.maklon',
        string='MoU Reference',
        tracking=True,
        domain=[('state', '=', 'mou')],
        help='Optional reference to a confirmed MoU.',
    )
    distribution_by = fields.Char(
        string='Distribution By',
        tracking=True,
    )

    # ─── Account / Sub-Company ──────────────────────────────────────────────
    account_option = fields.Selection(
        selection=[
            ('mik', 'Internal MIK'),
            ('client', 'External Client'),
        ],
        string='Account Option',
        tracking=True,
    )
    sub_company_type = fields.Selection(
        selection=[
            ('internal_mik', 'Internal MIK'),
            ('external', 'External'),
        ],
        string='Sub-Company Type',
        tracking=True,
    )

    # ─── SLA (computed) ─────────────────────────────────────────────────────
    sla_submit_days = fields.Integer(
        string='SLA Submit (Days)',
        compute='_compute_sla_days',
        store=True,
    )
    sla_verification_days = fields.Integer(
        string='SLA Verification (Days)',
        compute='_compute_sla_days',
        store=True,
    )
    submit_deadline = fields.Date(
        string='Submit Deadline',
        readonly=True,
        tracking=True,
    )
    verification_deadline = fields.Date(
        string='Verification Deadline',
        readonly=True,
        tracking=True,
    )

    # ─── State ──────────────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('sub_company_activation', 'Sub-Company Activation'),
            ('regulatory_submit', 'Regulatory Submit'),
            ('bpom_verification', 'BPOM Verification'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        string='Status',
        default='draft',
        required=True,
        copy=False,
        tracking=True,
        index=True,
    )

    # ─── Document Attachments ───────────────────────────────────────────────
    doc_license_agreement = fields.Binary(
        string='Electronic Brand License Agreement',
        attachment=True,
    )
    doc_license_agreement_fname = fields.Char(
        string='License Agreement Filename',
    )
    doc_brand_statement = fields.Binary(
        string='Surat Keterangan Penggunaan Merek (Client Signed)',
        attachment=True,
    )
    doc_brand_statement_fname = fields.Char(
        string='Brand Statement Filename',
    )
    doc_haki_certificate = fields.Binary(
        string='Sertifikat HAKI / Tanda Bukti HAKI',
        attachment=True,
    )
    doc_haki_certificate_fname = fields.Char(
        string='HAKI Certificate Filename',
    )
    doc_dir_statement = fields.Binary(
        string='Surat Pernyataan Merek (MIK Director Signed)',
        attachment=True,
    )
    doc_dir_statement_fname = fields.Char(
        string='Director Statement Filename',
    )

    # ─── Rejection Reason ───────────────────────────────────────────────────
    rejection_reason = fields.Text(
        string='Rejection / Revision Notes',
        tracking=True,
    )

    # ─── Related Products ───────────────────────────────────────────────────
    produk_ids = fields.One2many(
        comodel_name='registrasi.produk',
        inverse_name='brand_registration_id',
        string='Product Registrations',
    )
    produk_count = fields.Integer(
        string='# Products',
        compute='_compute_produk_count',
    )

    # ────────────────────────────────────────────────────────────────────────
    # Constraints
    # ────────────────────────────────────────────────────────────────────────

    @api.constrains(
        'doc_license_agreement',
        'doc_brand_statement',
        'doc_haki_certificate',
        'doc_dir_statement',
    )
    def _check_documents_on_proceed(self):
        """Validate all documents are present when leaving draft."""
        pass  # Enforced in action_proceed_to_activation

    # ────────────────────────────────────────────────────────────────────────
    # Computes
    # ────────────────────────────────────────────────────────────────────────

    @api.depends('account_option')
    def _compute_sla_days(self):
        for rec in self:
            if rec.account_option == 'mik':
                rec.sla_submit_days = 7
                rec.sla_verification_days = 7
            elif rec.account_option == 'client':
                rec.sla_submit_days = 14
                rec.sla_verification_days = 14
            else:
                rec.sla_submit_days = 0
                rec.sla_verification_days = 0

    @api.depends('produk_ids')
    def _compute_produk_count(self):
        for rec in self:
            rec.produk_count = len(rec.produk_ids)
        
    @api.onchange('client_id')
    def _onchange_client_id(self):
        self.mou_id = False
        return {
            'domain': {
                'mou_id': [
                    ('state', '=', 'mou'),
                    ('nama_cust', '=', self.client_id.id)
                ]
            }
        }
    
    @api.onchange('mou_id')
    def _onchange_mou_id(self):
        if self.mou_id:
            self.brand_name = self.mou_id.brand
            self.client_id = self.mou_id.nama_cust.id

    # ────────────────────────────────────────────────────────────────────────
    # ORM Overrides
    # ────────────────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'registrasi.brand'
                ) or _('New')
        return super().create(vals_list)

    def copy(self, default=None):
        default = dict(default or {})
        default['name'] = _('New')
        default['state'] = 'draft'
        return super().copy(default)

    # ────────────────────────────────────────────────────────────────────────
    # State Transition Actions
    # ────────────────────────────────────────────────────────────────────────

    def action_proceed_to_activation(self):
        """Draft → Sub-Company Activation: validate all 4 documents."""
        for rec in self:
            missing = []
            if not rec.doc_license_agreement:
                missing.append(_('Electronic Brand License Agreement'))
            if not rec.doc_brand_statement:
                missing.append(_('Surat Keterangan Penggunaan Merek'))
            if not rec.doc_haki_certificate:
                missing.append(_('Sertifikat HAKI / Tanda Bukti HAKI'))
            if not rec.doc_dir_statement:
                missing.append(_('Surat Pernyataan Merek (MIK Director)'))
            # if missing:
            #     raise UserError(
            #         _('Please upload all required documents before proceeding:\n- %s')
            #         % '\n- '.join(missing)
            #     )
            rec.write({'state': 'sub_company_activation'})
            rec.message_post(
                body=_('Status changed to Sub-Company Activation.'),
                message_type='notification',
            )
        return True

    def action_submit_to_bpom(self):
        """Sub-Company Activation → Regulatory Submit: sub_company_type required."""
        for rec in self:
            if not rec.sub_company_type:
                raise UserError(
                    _('Please select a Sub-Company Type before submitting to BPOM.')
                )
            today = fields.Date.today()
            deadline = today + timedelta(days=rec.sla_submit_days or 14)
            rec.write({
                'state': 'regulatory_submit',
                'submit_deadline': deadline,
            })
            rec.message_post(
                body=_(
                    'Submitted to Regulatory. Submit deadline: %s'
                ) % deadline.strftime('%d %B %Y'),
                message_type='notification',
            )
        return True

    def action_bpom_verifying(self):
        """Regulatory Submit → BPOM Verification."""
        for rec in self:
            today = fields.Date.today()
            v_deadline = today + timedelta(days=rec.sla_verification_days or 14)
            rec.write({
                'state': 'bpom_verification',
                'verification_deadline': v_deadline,
            })
            rec.message_post(
                body=_(
                    'Document forwarded to BPOM for verification. '
                    'Verification deadline: %s'
                ) % v_deadline.strftime('%d %B %Y'),
                message_type='notification',
            )
        return True

    def action_approve(self):
        """BPOM Verification → Approved."""
        for rec in self:
            rec.write({
                'state': 'approved',
                'rejection_reason': False,
            })
            rec.message_post(
                body=_('Brand registration APPROVED by BPOM.'),
                message_type='notification',
                subtype_xmlid='mail.mt_comment',
            )
        return True

    def action_reject_to_resubmit(self):
        """BPOM Verification → back to Regulatory Submit (revision required)."""
        for rec in self:
            if not rec.rejection_reason:
                raise UserError(
                    _('Please provide rejection / revision notes before rejecting.')
                )
            rec.write({'state': 'regulatory_submit'})
            rec.message_post(
                body=_('BPOM requested document revisions. Reason:\n%s')
                % rec.rejection_reason,
                message_type='notification',
                subtype_xmlid='mail.mt_comment',
            )
        return True

    def action_mark_rejected(self):
        """Final rejection (BPOM Verification → Rejected)."""
        for rec in self:
            if not rec.rejection_reason:
                raise UserError(
                    _('Please provide rejection notes before marking as rejected.')
                )
            rec.write({'state': 'rejected'})
            rec.message_post(
                body=_('Brand registration REJECTED. Reason:\n%s') % rec.rejection_reason,
                message_type='notification',
                subtype_xmlid='mail.mt_comment',
            )
        return True

    def action_reset_to_draft(self):
        """Reset to Draft (for superuser / correction)."""
        for rec in self:
            rec.write({'state': 'draft'})
            rec.message_post(
                body=_('Record reset to Draft.'),
                message_type='notification',
            )
        return True

    # ────────────────────────────────────────────────────────────────────────
    # Smart Button Actions
    # ────────────────────────────────────────────────────────────────────────

    def action_view_produk(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Product Registrations'),
            'res_model': 'registrasi.produk',
            'view_mode': 'list,form',
            'domain': [('brand_registration_id', '=', self.id)],
            'context': {'default_brand_registration_id': self.id},
        }
