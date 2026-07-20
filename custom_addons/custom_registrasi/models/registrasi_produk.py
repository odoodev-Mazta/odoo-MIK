from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta, date


class RegistrasiProduk(models.Model):
    _name = 'registrasi.produk'
    _description = 'Product NIE Registration to BPOM'
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

    # ─── Brand Link ─────────────────────────────────────────────────────────
    brand_registration_id = fields.Many2one(
        comodel_name='registrasi.brand',
        string='Brand Registration',
        required=True,
        ondelete='cascade',
        tracking=True,
        index=True,
        domain=lambda self: self._get_available_brand_domain(),
    )
    client_id = fields.Many2one(
        comodel_name='res.partner',
        string='Client',
        related='brand_registration_id.client_id',
        store=True,
        readonly=True,
    )

    # ─── Category ───────────────────────────────────────────────────────────
    category = fields.Selection(
        selection=[
            ('import', 'Import'),
            ('lokal', 'Lokal'),
        ],
        string='Category',
        required=True,
        tracking=True,
    )

    # ─── Confirmation Counter ───────────────────────────────────────────────

    # ─── State ──────────────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('form_request', 'Form Request (Approval)'),
            ('ro_drafting', 'RO Drafting'),
            ('submitted', 'Submitted to BPOM'),
            ('payment_request', 'Payment Request'),
            ('payment_verification', 'Payment Verification'),
            ('bpom_review', 'BPOM Review'),
            ('nie_issued', 'NIE Issued'),
            ('failed', 'Failed'),
        ],
        string='Status',
        default='draft',
        required=True,
        copy=False,
        tracking=True,
        index=True,
    )

    # ─── Module Integration: custom_mou ─────────────────────────────────────
    mou_id = fields.Many2one(
        comodel_name='draft.maklon',           
        string='MoU Reference',
        tracking=True,
        domain=[('state', '=', 'mou')],    
        help='Required for Import category. Must be a confirmed MOU.',
    )

    # # ─── Module Integration: custom_design ──────────────────────────────────
    # design_id = fields.Many2one(
    #     comodel_name='design.usulan',          
    #     string='Design Reference',
    #     tracking=True,
    #     domain=[('state', '=', 'done')],   
    #     help='Design artwork. Must be finished before submitting to BPOM.',
    # )

    design_sla_type = fields.Selection(
        selection=[
            ('standard', 'Standard (7 Days)'),
            ('custom', 'Custom (Manual)'),
        ],
        string='Design SLA Type',
        default='standard',
    )
    design_sla_days = fields.Integer(
        string='Design SLA (Days)',
        compute='_compute_design_sla_days',
        store=True,
    )

    # ─── Local Category: RnD & QC Integration ───────────────────────────────
    rnd_formula_ref = fields.Char(
        string='RnD Formula Reference',
        tracking=True,
    )
    raw_material_status = fields.Selection(
        selection=[
            ('incomplete', 'Incomplete'),
            ('complete', 'Complete'),
        ],
        string='Raw Material Status',
        default='incomplete',
        tracking=True,
    )
    qc_check_status = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('passed', 'Passed'),
            ('failed', 'Failed'),
        ],
        string='QC Check Status',
        default='pending',
        tracking=True,
    )
    purchasing_import_status = fields.Selection(
        selection=[
            ('waiting', 'Waiting'),
            ('received', 'Received'),
        ],
        string='Packaging Material Status',
        default='waiting',
        tracking=True,
    )
    moq_qty = fields.Integer(
        string='Minimum Order Quantity (MOQ)',
        digits=(16, 3),
    )

    # ─── Halal Specification ────────────────────────────────────────────────
    halal_type = fields.Selection(
        selection=[
            ('lokal', 'Lokal'),
            ('import', 'Import'),
        ],
        string='Halal Type',
        tracking=True,
    )
    halal_cert_attachment = fields.Binary(
        string='Halal Certificate',
        attachment=True,
    )
    halal_cert_fname = fields.Char(
        string='Halal Certificate Filename',
    )

    # ─── PNBP & Payment Documents ───────────────────────────────────────────
    doc_pnbp = fields.Binary(
        string='PNBP Document (Penerimaan Negara Bukan Pajak)',
        attachment=True,
        copy=False,
    )
    doc_pnbp_fname = fields.Char(
        string='PNBP Document Filename',
    )
    pnbp_notes = fields.Text(
        string='PNBP / Billing Notes',
    )

    # ─── BPOM Review Documents ──────────────────────────────────────────────
    doc_bpom_revision = fields.Binary(
        string='Revised Documents (BPOM Request)',
        attachment=True,
        copy=False,
    )
    doc_bpom_revision_fname = fields.Char(
        string='Revised Documents Filename',
    )
    bpom_review_notes = fields.Text(
        string='BPOM Review / Revision Notes',
        tracking=True,
    )
    bpom_review_deadline = fields.Date(
        string='BPOM Review Deadline (14 HK)',
        readonly=True,
        copy=False,
        tracking=True,
    )

    # ─── NIE Output ─────────────────────────────────────────────────────────

    # ─── Multi-Approval Fields ──────────────────────────────────────────────
    approved_by_marketing = fields.Many2one(
        comodel_name='res.users',
        string='Approved by Product Marketing',
        readonly=True,
        copy=False,
        tracking=True,
    )
    approved_date_marketing = fields.Datetime(
        string='Marketing Approval Date',
        readonly=True,
        copy=False,
    )
    approved_by_regulatory = fields.Many2one(
        comodel_name='res.users',
        string='Approved by Regulatory',
        readonly=True,
        copy=False,
        tracking=True,
    )
    approved_date_regulatory = fields.Datetime(
        string='Regulatory Approval Date',
        readonly=True,
        copy=False,
    )
    approved_by_factory = fields.Many2one(
        comodel_name='res.users',
        string='Approved by Factory Manager',
        readonly=True,
        copy=False,
        tracking=True,
    )
    approved_date_factory = fields.Datetime(
        string='Factory Approval Date',
        readonly=True,
        copy=False,
    )
    approval_state = fields.Selection(
        selection=[
            ('waiting_marketing', 'Waiting Marketing Approval'),
            ('waiting_regulatory', 'Waiting Regulatory Approval'),
            ('waiting_factory', 'Waiting Factory Manager Approval'),
            ('all_approved', 'All Approved'),
        ],
        string='Approval Progress',
        compute='_compute_approval_state',
        store=True,
    )

    # ─── Product Lines ──────────────────────────────────────────────────────
    product_line_ids = fields.One2many(
        comodel_name='registrasi.produk.line',
        inverse_name='produk_id',
        string='Product Lines',
    )

    # ─── Deadlines ──────────────────────────────────────────────────────────
    submit_deadline = fields.Date(
        string='Submit Deadline',
        copy=False,
        tracking=True,
    )

    def _get_available_brand_domain(self):
        issued_brand_ids = self.env['registrasi.produk'].search([
            ('state', '=', 'nie_issued'),
        ]).mapped(
            'brand_registration_id'
        ).ids

        return [
            ('state', '=', 'approved'),
            ('id', 'not in', issued_brand_ids),
        ]

    # ────────────────────────────────────────────────────────────────────────
    # Computes
    # ────────────────────────────────────────────────────────────────────────

    @api.depends('design_sla_type')
    def _compute_design_sla_days(self):
        for rec in self:
            if rec.design_sla_type == 'standard':
                rec.design_sla_days = 7
            else:
                rec.design_sla_days = 0  # Manual / custom

    @api.depends(
        'approved_by_marketing',
        'approved_by_regulatory',
        'approved_by_factory',
    )
    def _compute_approval_state(self):
        for rec in self:
            if not rec.approved_by_marketing:
                rec.approval_state = 'waiting_marketing'
            elif not rec.approved_by_regulatory:
                rec.approval_state = 'waiting_regulatory'
            elif not rec.approved_by_factory:
                rec.approval_state = 'waiting_factory'
            else:
                rec.approval_state = 'all_approved'

    # ────────────────────────────────────────────────────────────────────────
    # Onchange
    # ────────────────────────────────────────────────────────────────────────

    @api.onchange('category')
    def _onchange_category(self):
        """Clear MoU when category changes away from import."""
        if self.category != 'import':
            self.mou_id = False

    @api.onchange('mou_id')
    def _onchange_mou_id(self):
        """Warn if selected MoU does not contain this product."""
        pass  # Validation done in Python constraint]

    @api.onchange('brand_registration_id')
    def _onchange_brand_registration_id(self):
        if self.brand_registration_id and self.brand_registration_id.mou_id:
            self.mou_id = self.brand_registration_id.mou_id
        else:
            self.mou_id = False

    # ────────────────────────────────────────────────────────────────────────
    # Constraints
    # ────────────────────────────────────────────────────────────────────────

    @api.constrains('category', 'mou_id')
    def _check_mou_required_for_import(self):
        for rec in self:
            if rec.category == 'import' and not rec.mou_id:
                raise ValidationError(
                    _('An MoU Reference is mandatory for Import category products.')
                )

    # ────────────────────────────────────────────────────────────────────────
    # ORM Overrides
    # ────────────────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'registrasi.produk'
                ) or _('New')
        return super().create(vals_list)

    # def copy(self, default=None):
    #     default = dict(default or {})
    #     default['name'] = _('New')
    #     default['state'] = 'draft'
    #     default['confirmation_counter'] = 0
    #     default['approved_by_marketing'] = False
    #     default['approved_by_regulatory'] = False
    #     default['approved_by_factory'] = False
    #     return super().copy(default)
    def copy(self, default=None):
        default = dict(default or {})
        default['name'] = _('New')
        default['state'] = 'draft'

        new_record = super().copy(default)
        for line in new_record.product_line_ids:
            line.write({
                'confirmation_counter': 0,
                'product_name_revision_count': 0,
                'product_template_id': False,
            })

        return new_record

    def write(self, vals):
        res = super().write(vals)

        for rec in self:
            for line in rec.product_line_ids:
                if (
                        line.confirmation_counter > 3
                        and rec.state not in ('failed', 'nie_issued')
                ):
                    rec._action_auto_fail()

        return res

    # ────────────────────────────────────────────────────────────────────────
    # Internal Helpers
    # ────────────────────────────────────────────────────────────────────────

    def _check_all_approved(self):
        """Return True if all 3 approvals are complete."""
        self.ensure_one()
        return bool(
            self.approved_by_marketing
            and self.approved_by_regulatory
            and self.approved_by_factory
        )

    def _action_auto_fail(self):
        self.ensure_one()
        self.write({'state': 'failed'})
        self.message_post(
            body=_(
                'Registration automatically FAILED: BPOM confirmation counter '
                'exceeded the maximum of 3 revisions.'
            ),
            message_type='notification',
            subtype_xmlid='mail.mt_comment',
        )

    def _get_current_user_approval_role(self):
        """Detect which approval role the current user belongs to."""
        user = self.env.user
        marketing_group = self.env.ref(
            'custom_registrasi.group_registrasi_product_marketing',
            raise_if_not_found=False,
        )
        regulatory_group = self.env.ref(
            'custom_registrasi.group_registrasi_regulatory',
            raise_if_not_found=False,
        )
        factory_group = self.env.ref(
            'custom_registrasi.group_registrasi_factory_manager',
            raise_if_not_found=False,
        )
        if marketing_group and user in marketing_group.users:
            return 'marketing'
        if regulatory_group and user in regulatory_group.users:
            return 'regulatory'
        if factory_group and user in factory_group.users:
            return 'factory'
        return None

    # ────────────────────────────────────────────────────────────────────────
    # State Transition Actions
    # ────────────────────────────────────────────────────────────────────────

    def action_submit_form_request(self):
        """Draft → Form Request (Approval)."""
        for rec in self:
            # if rec.category == 'import' and not rec.mou_id:
            #     raise UserError(
            #         _('An MoU Reference is required for Import category before requesting approval.')
            #     )
            # if not rec.product_line_ids:
            #     raise UserError(
            #         _('Please add at least one product line before submitting.')
            #     )
            rec.write({'state': 'form_request'})
            rec.message_post(
                body=_('Form Request submitted. Awaiting 3-tier approval.'),
                message_type='notification',
            )
        return True

    # ── 3-Tier Approval ─────────────────────────────────────────────────────

    def action_approve_marketing(self):
        """Tier 1: Product Marketing approval."""
        for rec in self:
            if rec.state != 'form_request':
                raise UserError(_('Record must be in Form Request state to approve.'))
            if rec.approved_by_marketing:
                raise UserError(_('Marketing approval has already been given.'))
            rec.write({
                'approved_by_marketing': self.env.uid,
                'approved_date_marketing': fields.Datetime.now(),
            })
            rec.message_post(
                body=_('Tier 1 – Product Marketing approved by %s.')
                % self.env.user.name,
                message_type='notification',
            )
            # Auto-progress if all approvals done
            if rec._check_all_approved():
                rec._action_move_to_ro_drafting()
        return True

    def action_approve_regulatory(self):
        """Tier 2: Regulatory approval."""
        for rec in self:
            if rec.state != 'form_request':
                raise UserError(_('Record must be in Form Request state to approve.'))
            if not rec.approved_by_marketing:
                raise UserError(
                    _('Marketing approval (Tier 1) must be completed first.')
                )
            if rec.approved_by_regulatory:
                raise UserError(_('Regulatory approval has already been given.'))
            rec.write({
                'approved_by_regulatory': self.env.uid,
                'approved_date_regulatory': fields.Datetime.now(),
            })
            rec.message_post(
                body=_('Tier 2 – Regulatory approved by %s.') % self.env.user.name,
                message_type='notification',
            )
            if rec._check_all_approved():
                rec._action_move_to_ro_drafting()
        return True

    def action_approve_factory(self):
        """Tier 3: Factory Manager approval."""
        for rec in self:
            if rec.state != 'form_request':
                raise UserError(_('Record must be in Form Request state to approve.'))
            if not rec.approved_by_regulatory:
                raise UserError(
                    _('Regulatory approval (Tier 2) must be completed first.')
                )
            if rec.approved_by_factory:
                raise UserError(_('Factory Manager approval has already been given.'))
            rec.write({
                'approved_by_factory': self.env.uid,
                'approved_date_factory': fields.Datetime.now(),
            })
            rec.message_post(
                body=_('Tier 3 – Factory Manager approved by %s.') % self.env.user.name,
                message_type='notification',
            )
            if rec._check_all_approved():
                rec._action_move_to_ro_drafting()
        return True

    def _action_move_to_ro_drafting(self):
        """Internal: move to RO Drafting after all approvals."""
        self.ensure_one()
        self.write({'state': 'ro_drafting'})
        self.message_post(
            body=_('All 3 approval tiers completed. Record moved to RO Drafting.'),
            message_type='notification',
            subtype_xmlid='mail.mt_comment',
        )

    # ── RO Drafting → Submitted ──────────────────────────────────────────────

    def action_confirm_official_name_and_submit(self):
        for rec in self:
            # if not rec.design_id:
            #     raise UserError(_('A Design Reference must be selected before submitting to BPOM.'))
            # # GANTI — design.usulan tidak punya state 'available'
            # if rec.design_id.state != 'done':
            #     raise UserError(
            #         _('The linked Design must be in "Selesai" status. Current: %s')
            #         % dict(rec.design_id._fields['state'].selection).get(rec.design_id.state, '')
            #     )
            invalid_lines = rec.product_line_ids.filtered(
                lambda line: not line.official_product_name
            )

            if invalid_lines:
                raise UserError(
                    _('All products must have Official Product Name.')
                )

            today = fields.Date.today()

            rec.write({
                'state': 'submitted',
                'submit_deadline': today + timedelta(days=7),
            })

            # Ambil semua nama produk untuk chatter
            product_names = "\n".join(
                [
                    f"- {line.product_template_id.display_name}: {line.official_product_name}"
                    for line in rec.product_line_ids
                ]
            )

            rec.message_post(
                body=_(
                    'Product submitted to BPOM.\n\n'
                    'Official Product Names:\n%s'
                ) % product_names,
                message_type='notification',
            )
        return True

    # ── Submitted → Payment Request ──────────────────────────────────────────

    def action_request_payment(self):
        """Submitted → Payment Request. PNBP document required."""
        for rec in self:
            # if not rec.doc_pnbp:
            #     raise UserError(
            #         _('Please upload the PNBP (Penerimaan Negara Bukan Pajak) '
            #           'document before requesting payment.')
            #     )
            rec.write({'state': 'payment_request'})
            rec.message_post(
                body=_('Payment request sent to Finance with attached PNBP document.'),
                message_type='notification',
            )
        return True

    # ── Payment Request → Payment Verification ────────────────────────────────

    def action_finance_approve_payment(self):
        """Finance: Payment Request → Payment Verification → BPOM Review."""
        for rec in self:
            rec.write({
                'state': 'bpom_review',
                'bpom_review_deadline': fields.Date.today() + timedelta(days=14),
            })
            rec.message_post(
                body=_(
                    'Payment verified by Finance (%s). Record automatically moved '
                    'to BPOM Review. Review deadline: %s'
                ) % (
                    self.env.user.name,
                    (fields.Date.today() + timedelta(days=14)).strftime('%d %B %Y'),
                ),
                message_type='notification',
                subtype_xmlid='mail.mt_comment',
            )
        return True

    # ── BPOM Review ──────────────────────────────────────────────────────────

    def action_resubmit_to_bpom(self):
        """Re-submit revised documents to BPOM (from bpom_review state).
        Increments confirmation_counter. Auto-fails at >3."""
        for rec in self:
            # if not rec.doc_bpom_revision:
            #     raise UserError(
            #         _('Please upload the revised documents before re-submitting to BPOM.')
            #     )
            for line in rec.product_line_ids:
                new_counter = line.confirmation_counter + 1

                if new_counter > 3:
                    line.write({
                        'confirmation_counter': new_counter
                    })

                    rec.write({
                        'state': 'failed'
                    })

                    rec.message_post(
                        body=_(
                            '❌ Product %s failed: '
                            'maximum BPOM revision exceeded.'
                        ) % line.product_name
                    )
                else:
                    line.write({
                        'confirmation_counter': new_counter
                    })

            rec.message_post(
                body=_(
                    'Product revision submitted to BPOM.'
                )
            )
        return True

    def action_revise_product_name(self):
        """RO requests product name revision during BPOM Review.
        Max 2 name revisions."""
        for rec in self:
            for line in rec.product_line_ids:

                if line.product_name_revision_count >= 2:
                    raise UserError(
                        _('Product name revision maximum reached.')
                    )

                line.write({
                    'product_name_revision_count':
                        line.product_name_revision_count + 1,

                    'official_product_name':
                        False,
                })

            rec.write({
                'state': 'ro_drafting'
            })
        return True

    def action_issue_nie(self):
        """BPOM Review → NIE Issued. Creates / links product.template."""
        for rec in self:
            for line in rec.product_line_ids:

                if not line.nie_number:
                    raise UserError(
                        _('Please enter NIE number for %s')
                        % line.product_name
                    )

                product = line._create_or_link_product_template()

                line.write({
                    'product_template_id': product.id
                })

            rec.write({
                'state': 'nie_issued'
            })
        return True

    # def _create_or_link_product_template(self):
    #
    #     ProductTemplate = self.env['product.template']
    #
    #     existing = ProductTemplate.search(
    #         [
    #             ('default_code', '=', self.nie_number)
    #         ],
    #         limit=1
    #     )
    #
    #     if existing:
    #         return existing
    #
    #     return ProductTemplate.create({
    #
    #         'name':
    #             self.official_product_name
    #             or self.product_name,
    #
    #         'default_code':
    #             self.nie_number,
    #
    #         'type':
    #             'consu',
    #
    #         'description':
    #             _(
    #                 'Created from NIE Registration %s'
    #             ) % self.produk_id.name
    #
    #     })

    # ────────────────────────────────────────────────────────────────────────
    # Button: Reset to Draft
    # ────────────────────────────────────────────────────────────────────────

    def action_reset_to_draft(self):
        """Reset to Draft (superuser / correction)."""
        for rec in self:
            rec.write({'state': 'draft'})
            rec.message_post(
                body=_('Record reset to Draft.'),
                message_type='notification',
            )
    def action_view_produk(self):
        """Smart button: open linked Odoo product."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Odoo Product'),
            'res_model': 'product.template',
            'view_mode': 'form',
            'res_id': self.product_template_id.id,
            'target': 'current',
        }