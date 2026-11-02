from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    mou_id = fields.Many2one(
        'draft.maklon',
        string='No. MOU',
        domain="[('state', '=', 'mou'), ('nama_cust', '=', partner_id)]"
    )

    timeline_stage = fields.Selection([
        ('reg',  'Biaya Registrasi'),
        ('dp',   'Down Payment'),
        ('nie',  'Tagihan NIE'),
        ('bp' , 'Balance Payment'),
    ], string='Tahapan (Data Lama)', copy=False,
        help="Hanya untuk SO lama. Tahapan SO baru dipilih di Customer Payment.")

    is_repeat_order = fields.Boolean(
        string='Repeat Order?',
        default=False,
        copy=False,
    )

    brand_name = fields.Char(
        string='Nama Brand',
        compute='_compute_brand_name',
        store=True,
        readonly=False,
        help="Terisi dari MOU jika brand sudah terdaftar. "
             "Jika belum ada, bisa diisi manual sambil menunggu brand disetujui.",
    )

    mou_payment_ids = fields.One2many(
        'account.payment', 'sale_order_id', string='Customer Payments')
    mou_payment_count = fields.Integer(
        string='Jumlah Payment', compute='_compute_mou_payment_count')

    @api.depends('mou_id', 'mou_id.brand')
    def _compute_brand_name(self):
        for order in self:
            order.brand_name = order.mou_id.brand or order.brand_name

    @api.depends('mou_payment_ids')
    def _compute_mou_payment_count(self):
        for order in self:
            order.mou_payment_count = len(order.mou_payment_ids)

    def action_view_mou_payments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Customer Payments',
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'domain': [('sale_order_id', '=', self.id)],
            'context': {
                'default_payment_type': 'inbound',
                'default_partner_type': 'customer',
                'default_partner_id': self.partner_id.id,
                'default_mou_id': self.mou_id.id,
                'default_sale_order_id': self.id,
            },
        }

    # @api.depends('mou_id')
    # def _compute_is_repeat_order(self):
    #     for order in self:
    #         if order.mou_id:
    #             paid_reg_invoice = self.env['account.move'].search([
    #                 ('mou_id', '=', order.mou_id.id),
    #                 ('timeline_stage', '=', 'reg'),
    #                 ('payment_state', 'in', ('in_payment', 'paid')),
    #                 ('state', '=', 'posted'),
    #             ], limit=1)
    #             order.is_repeat_order = bool(paid_reg_invoice)
    #         else:
    #             order.is_repeat_order = False
    
    def onchange(self, values, field_names, fields_spec):
        """Nomor diketik manual: form baru dibuka dengan nomor kosong."""
        result = super().onchange(values, field_names, fields_spec)
        if not self and not field_names and 'name' in fields_spec and not self.env.context.get('default_name'):
            result.setdefault('value', {})['name'] = False
        return result

    @api.constrains('name', 'company_id')
    def _check_unique_number(self):
        for rec in self:
            if rec.name and rec.name != 'New' and self.search_count([
                ('id', '!=', rec.id),
                ('name', '=', rec.name),
                ('company_id', '=', rec.company_id.id),
            ]):
                raise ValidationError(f'Nomor {rec.name} sudah dipakai.')

    @api.onchange('partner_id')
    def _onchange_partner_id_reset_mou(self):
        self.mou_id = False
        self.brand_name = False

    @api.onchange('mou_id', 'timeline_stage')
    def _onchange_mou_id_fill_lines(self):
        """
        Saat No. MOU dipilih (atau tahapan diganti), isi order_line otomatis
        dari data draft.maklon.maklon_line_ids.

        - Untuk tahapan 'bp' (Balance Payment): hitung proporsional dari SISA
        tunggakan kontrak (logic lama, dipertahankan).
        - Selain itu: isi langsung dari HNA per baris produk MOU
        (tanpa proporsi sisa tunggakan).
        """
        if not self.mou_id:
            self.order_line = [(5, 0, 0)]
            return

        mou = self.mou_id
        if not mou.maklon_line_ids:
            self.order_line = [(5, 0, 0)]
            return

        tax_11 = False
        if mou.is_ppn:
            tax_11 = self.env['account.tax'].search([
                ('amount', '=', 11),
                ('amount_type', '=', 'percent'),
                ('type_tax_use', '=', 'sale'),
                ('active', '=', True),
            ], limit=1)

        # ═══════════════════════════════════════════════════════════════
        # TAHAPAN BP: proporsional dari sisa tunggakan (logic lama)
        # ═══════════════════════════════════════════════════════════════
        if self.timeline_stage == 'bp':
            total_dpp = sum(
                l.product_qty * l.product_hna * (1 - (l.diskon or 0.0) / 100.0)
                for l in mou.maklon_line_ids
            )
            if total_dpp <= 0:
                return

            total_kontrak = mou.nilai_kontrak or 0.0

            dp_invoices = self.env['account.move'].search([
                ('mou_id', '=', mou.id),
                ('state', '=', 'posted'),
                ('move_type', 'in', ('out_invoice', 'out_refund')),
                ('timeline_stage', '=', 'dp'),
            ])

            total_dp = sum(
                inv.amount_total if inv.move_type == 'out_invoice' else -inv.amount_total
                for inv in dp_invoices
            )

            sisa_tunggakan = total_kontrak - total_dp
            if sisa_tunggakan <= 0:
                self.order_line = [(5, 0, 0)]
                return

            sisa_tunggakan_dpp = (sisa_tunggakan / 1.11) if mou.is_ppn else sisa_tunggakan

            new_lines = [(5, 0, 0)]
            for line in mou.maklon_line_ids:
                dpp_line = line.product_qty * line.product_hna * (1 - (line.diskon or 0.0) / 100.0)
                if dpp_line <= 0:
                    continue
                proporsi = dpp_line / total_dpp
                alokasi_dpp = sisa_tunggakan_dpp * proporsi
                qty = line.product_qty or 1.0
                price_unit = alokasi_dpp / qty

                vals = {
                    'product_id': line.product.id,
                    'product_uom_qty': qty,
                    'price_unit': price_unit,
                    'name': f"{line.product.display_name} - Pelunasan Balance Payment",
                    'tax_ids': [(6, 0, tax_11.ids)] if tax_11 else [(5, 0, 0)],
                }
                new_lines.append((0, 0, vals))

            self.order_line = new_lines
            return

        # ═══════════════════════════════════════════════════════════════
        # SO BARU / TAHAPAN LAIN: isi langsung dari HNA per baris
        # ═══════════════════════════════════════════════════════════════
        stage_label_map = {
            'reg':  'Biaya Registrasi',
            'dp':   'Down Payment',
            'nie':  'Tagihan NIE',
        }
        label_suffix = stage_label_map.get(self.timeline_stage, '')

        new_lines = [(5, 0, 0)]
        for line in mou.maklon_line_ids:
            qty = line.product_qty or 1.0
            harga_setelah_diskon = line.product_hna * (1 - (line.diskon or 0.0) / 100.0)

            vals = {
                'product_id': line.product.id,
                'product_uom_qty': qty,
                'price_unit': harga_setelah_diskon,
                'name': f"{line.product.display_name} - {label_suffix}" if label_suffix else line.product.display_name,
                'tax_ids': [(6, 0, tax_11.ids)] if tax_11 else [(5, 0, 0)],
            }
            new_lines.append((0, 0, vals))

        self.order_line = new_lines

    def _prepare_invoice(self):
        self.ensure_one()
        vals = super()._prepare_invoice()
        if self.mou_id:
            vals.update({
                'mou_id': self.mou_id.id,
                'timeline_stage': self.timeline_stage,
            })
        return vals


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'

    def _create_invoice(self, order, so_line, amount):
        invoice = super()._create_invoice(order, so_line, amount)
        if invoice and order.mou_id:
            invoice.write({
                'mou_id': order.mou_id.id,
                'timeline_stage': order.timeline_stage,
            })
        return invoice


class AccountPaymentRegister(models.TransientModel):
    """Tombol Pay di invoice: No. MOU dan tahapan ikut terisi dari invoice."""
    _inherit = 'account.payment.register'

    mou_invoice_id = fields.Many2one(
        'account.move', compute='_compute_mou_invoice', store=True)
    mou_id = fields.Many2one(
        'draft.maklon', string='No. MOU', compute='_compute_mou_invoice', store=True)
    # Compute terpisah: tahapan bisa diubah user tanpa mengosongkan No. MOU.
    timeline_stage = fields.Selection([
        ('reg', 'Biaya Registrasi'),
        ('dp', 'Down Payment'),
        ('nie', 'Tagihan NIE'),
        ('bp', 'Balance Payment'),
    ], string='Tahapan', compute='_compute_timeline_stage', store=True, readonly=False)

    @api.depends('line_ids')
    def _compute_mou_invoice(self):
        for wizard in self:
            invoice = wizard.line_ids.move_id
            single = len(invoice) == 1 and invoice.move_type == 'out_invoice' and invoice.mou_id
            wizard.mou_invoice_id = invoice if single else False
            wizard.mou_id = invoice.mou_id if single else False

    @api.depends('mou_invoice_id')
    def _compute_timeline_stage(self):
        for wizard in self:
            invoice = wizard.mou_invoice_id
            if not invoice:
                wizard.timeline_stage = False
            elif invoice.timeline_stage:
                wizard.timeline_stage = invoice.timeline_stage
            else:
                # Invoice belum pernah dibayar = DP, sudah pernah = pelunasan.
                paid_before = self.env['account.payment'].search_count([
                    ('sale_invoice_id', '=', invoice.id),
                    ('state', 'in', ('in_process', 'paid')),
                ]) or invoice.currency_id.compare_amounts(invoice.amount_residual, invoice.amount_total) < 0
                wizard.timeline_stage = 'bp' if paid_before else 'dp'

    def _mou_payment_vals(self):
        if not self.mou_id:
            return {}
        return {
            'mou_id': self.mou_id.id,
            'timeline_stage': self.timeline_stage,
            'sale_invoice_id': self.mou_invoice_id.id,
        }

    @api.depends('mou_invoice_id')
    def _compute_amount(self):
        """Nominal awal tidak boleh melebihi sisa tagihan yang sebenarnya."""
        super()._compute_amount()
        for wizard in self:
            invoice = wizard.mou_invoice_id
            if invoice and not wizard.custom_user_amount and wizard.currency_id == invoice.currency_id:
                wizard.amount = min(wizard.amount, max(invoice._get_mou_outstanding(), 0.0))

    def _create_payment_vals_from_wizard(self, batch_result):
        vals = super()._create_payment_vals_from_wizard(batch_result)
        vals.update(self._mou_payment_vals())
        return vals

    def _create_payment_vals_from_batch(self, batch_result):
        vals = super()._create_payment_vals_from_batch(batch_result)
        vals.update(self._mou_payment_vals())
        return vals


class AccountMove(models.Model):
    _inherit = 'account.move'

    mou_id = fields.Many2one(
        'draft.maklon',
        string='No. MOU',
        readonly=False,
        copy=False,
        domain="[('state', '=', 'mou'), ('nama_cust', '=', partner_id)]"
    )

    timeline_stage = fields.Selection([
        ('reg',  'Biaya Registrasi'),
        ('dp',   'Down Payment'),
        ('nie',  'Tagihan NIE'),
        ('bp', 'Balance Payment'),
    ], string='Tahapan (Data Lama)', readonly=False, copy=False)

    def _get_mou_outstanding(self, exclude_payments=None):
        """Sisa invoice dikurangi payment yang belum punya jurnal entry,
        karena payment itu belum mengurangi residual invoice."""
        self.ensure_one()
        payments = self.matched_payment_ids | self.env['account.payment'].search([
            ('sale_invoice_id', '=', self.id),
        ])
        pending = payments.filtered(
            lambda pay: pay.state in ('in_process', 'paid') and not pay.move_id
        )
        if exclude_payments:
            pending -= exclude_payments
        return self.amount_residual - sum(pending.mapped('amount'))

    # ── Mapping timeline_stage invoice → state mou.setup ─────────────────────
    # timeline_stage di invoice pakai 'reg','dp','nie','bp'
    # state di mou.setup pakai 'biaya_registrasi','dp','nie','bp'
    _STAGE_TO_SETUP_STATE = {
        'reg':  'biaya_registrasi',
        'dp':   'dp',
        'nie':  'nie',
        'bp' : 'bp',
    }

    def _get_or_create_setup(self, mou_id, stage):
        """
        Cari mou.setup yang matching mou_id + state.
        Kalau tidak ada → buat baru otomatis (untuk data dari Sales Order).
        Ini memastikan data baru via SO tidak perlu entry manual di mou.setup.
        """
        setup_state = self._STAGE_TO_SETUP_STATE.get(stage)
        if not setup_state:
            return None

        # Cari setup yang matching mou + state tahapan
        setup = self.env['mou.setup'].search([
            ('mou_id', '=', mou_id),
            ('state',  '=', setup_state),
        ], limit=1)

        # Kalau belum ada → auto-create
        if not setup:
            mou = self.env['draft.maklon'].browse(mou_id)
            setup = self.env['mou.setup'].create({
                'name': f'AUTO/{setup_state.upper()}/{mou.draft_name or mou_id}',
                'mou_id': mou_id,
                'state': setup_state,
                'date': fields.Date.today(),
                'keterangan': 'Auto-created dari Sales Order',
            })
        return setup

    def action_post(self):
        res = super().action_post()
        self._sync_due_date_to_setup()
        return res

    def _sync_due_date_to_setup(self):
        due_field_map = {
            'reg':  'reg_due_date',
            'dp':   'dp_due_date',
            'nie':  'nie_due_date',
            'bp' : 'bp_due_date',
        }
        nilai_field_map = {
            'reg':  'reg_nilai',
            'dp':   'dp_nilai',
            'nie':  'nie_nilai',
            'bp' : 'bp_nilai',
        }
        for move in self:
            if move.move_type != 'out_invoice':
                continue
            if not move.mou_id or not move.timeline_stage:
                continue

            setup = self._get_or_create_setup(
                move.mou_id.id, move.timeline_stage
            )
            if not setup:
                continue

            write_vals = {}
            due_field   = due_field_map.get(move.timeline_stage)
            nilai_field = nilai_field_map.get(move.timeline_stage)

            if due_field and move.invoice_date_due:
                write_vals[due_field] = move.invoice_date_due
            if nilai_field and move.amount_untaxed:
                write_vals[nilai_field] = move.amount_untaxed

            if write_vals:
                setup.write(write_vals)
                # write() di mou.setup otomatis trigger _sync_to_container()

    def _compute_payment_state(self):
        super()._compute_payment_state()
        for move in self:
            if move.move_type != 'out_invoice':
                continue
            if not move.mou_id or not move.timeline_stage:
                continue
            if move.payment_state not in ('in_payment', 'paid'):
                continue
            move._sync_payment_date_to_setup()

    def _sync_payment_date_to_setup(self):
        payment_field_map = {
            'reg':  'reg_payment_date',
            'dp':   'dp_payment_date',
            'nie':  'nie_payment_date',
            'bp' : 'bp_payment_date',
        }
        pay_field = payment_field_map.get(self.timeline_stage)
        if not pay_field:
            return

        setup = self._get_or_create_setup(
            self.mou_id.id, self.timeline_stage
        )
        if not setup:
            return

        # Jangan overwrite 
        if setup[pay_field]:
            return

        payments = self._get_reconciled_payments()
        pay_date = payments[0].date if payments else fields.Date.today()
        setup.write({pay_field: pay_date})


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    mou_id = fields.Many2one(
        'draft.maklon',
        string='No. MOU',
        domain="[('state', '=', 'mou'), ('nama_cust', '=', partner_id)]"
    )

    timeline_stage = fields.Selection([
        ('reg', 'Biaya Registrasi'),
        ('dp', 'Down Payment'),
        ('nie', 'Tagihan NIE'),
        ('bp', 'Balance Payment'),
    ], string='Tahapan', copy=False)

    sale_invoice_id = fields.Many2one(
        'account.move',
        string='Sales Invoice',
        copy=False,
        domain="[('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),"
               " ('mou_id', '=', mou_id), ('amount_residual', '>', 0)]",
        help="Invoice yang dibayar. DP dan BP selalu membayar Sales Invoice dari SO.",
    )

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        compute='_compute_sale_order_id',
        store=True,
        readonly=False,
        copy=False,
    )

    so_outstanding_amount = fields.Monetary(
        string='Sisa Tagihan Invoice',
        compute='_compute_so_outstanding_amount',
    )
    sale_invoice_total = fields.Monetary(
        string='Total Invoice', related='sale_invoice_id.amount_total')
    sale_invoice_paid = fields.Monetary(
        string='Sudah Dibayar', compute='_compute_so_outstanding_amount')

    bukti_bayar_ids = fields.Many2many(
        'ir.attachment',
        'account_payment_bukti_bayar_rel',
        'payment_id',
        'attachment_id',
        string='Bukti Bayar',
        copy=False,
    )

    _STAGE_SETUP_FIELDS = {
        'reg': ('reg_nilai', 'reg_payment_date', 'reg_due_date'),
        'dp': ('dp_nilai', 'dp_payment_date', 'dp_due_date'),
        'nie': ('nie_nilai', 'nie_payment_date', 'nie_due_date'),
        'bp': ('bp_nilai', 'bp_payment_date', 'bp_due_date'),
    }
    _STAGES_WITH_SO = ('dp', 'bp')

    @api.depends('sale_invoice_id')
    def _compute_sale_order_id(self):
        for payment in self:
            order = payment.sale_invoice_id.line_ids.sale_line_ids.order_id[:1]
            payment.sale_order_id = order or payment.sale_order_id

    def _get_invoice_outstanding(self):
        self.ensure_one()
        return self.sale_invoice_id._origin._get_mou_outstanding(exclude_payments=self._origin)

    @api.depends('sale_invoice_id', 'timeline_stage')
    def _compute_so_outstanding_amount(self):
        for payment in self:
            payment.so_outstanding_amount = (
                payment._get_invoice_outstanding()
                if payment.sale_invoice_id and payment.timeline_stage in self._STAGES_WITH_SO
                else 0.0
            )
            payment.sale_invoice_paid = (
                payment.sale_invoice_id.amount_total - payment.so_outstanding_amount
                if payment.sale_invoice_id else 0.0
            )

    @api.onchange('mou_id')
    def _onchange_mou_id(self):
        if self.mou_id:
            self.partner_id = self.mou_id.nama_cust
        if self.sale_invoice_id.mou_id != self.mou_id:
            self.sale_invoice_id = False
            self.sale_order_id = False

    @api.onchange('timeline_stage')
    def _onchange_timeline_stage(self):
        if self.timeline_stage not in self._STAGES_WITH_SO:
            self.sale_invoice_id = False
            self.sale_order_id = False

    @api.onchange('sale_invoice_id')
    def _onchange_fill_invoice_amount(self):
        """Nominal awal = sisa tagihan invoice. Tetap bisa diedit untuk bayar sebagian."""
        if self.sale_invoice_id:
            self.amount = max(self.so_outstanding_amount, 0.0)
            self.currency_id = self.sale_invoice_id.currency_id

    def _check_mou_payment(self):
        for payment in self:
            if payment.payment_type != 'inbound' or payment.partner_type != 'customer':
                continue
            if not payment.mou_id and not payment.timeline_stage:
                continue
            if not payment.mou_id or not payment.timeline_stage:
                raise UserError('No. MOU dan Tahapan harus diisi bersamaan.')
            if payment.timeline_stage not in self._STAGES_WITH_SO:
                continue

            invoice = payment.sale_invoice_id
            if not invoice:
                raise UserError('Pembayaran DP/BP harus memilih Sales Invoice.')
            if invoice.state != 'posted' or invoice.move_type != 'out_invoice':
                raise UserError(f'Invoice {invoice.name} belum di-posting.')
            if invoice.mou_id != payment.mou_id:
                raise UserError('Sales Invoice tidak sesuai dengan No. MOU yang dipilih.')
            if payment.currency_id == invoice.currency_id:
                outstanding = payment._get_invoice_outstanding()
                if payment.currency_id.compare_amounts(payment.amount, outstanding) > 0:
                    raise UserError(
                        f'Nominal {payment.amount:,.2f} melebihi sisa tagihan '
                        f'invoice {invoice.name} sebesar {outstanding:,.2f}.'
                    )

    def _reconcile_with_sale_order(self):
        """Kurangi Sales Invoice yang dipilih. Payment tanpa jurnal entry hanya ditautkan."""
        for payment in self:
            invoice = payment.sale_invoice_id
            if payment.timeline_stage not in self._STAGES_WITH_SO or not invoice:
                continue
            payment.invoice_ids = [(4, invoice.id)]
            payment_lines = payment.move_id.line_ids.filtered(
                lambda line: line.account_id.account_type == 'asset_receivable'
                and not line.reconciled
            )
            invoice_lines = invoice.line_ids.filtered(
                lambda line: line.account_id in payment_lines.account_id
                and not line.reconciled
            )
            if payment_lines and invoice_lines:
                (payment_lines + invoice_lines).reconcile()

    def _sync_mou_tracking(self):
        """Tulis nilai dan tanggal per tahapan ke mou.setup, yang lanjut ke tracking."""
        for mou, stage in {(pay.mou_id, pay.timeline_stage) for pay in self if pay.mou_id and pay.timeline_stage}:
            payments = self.search([
                ('mou_id', '=', mou.id),
                ('timeline_stage', '=', stage),
                ('state', 'in', ('in_process', 'paid')),
            ])
            # Invoice lama masih bertahapan; invoice dari SO baru tidak.
            legacy_invoices = self.env['account.move'].search([
                ('mou_id', '=', mou.id),
                ('timeline_stage', '=', stage),
                ('state', '=', 'posted'),
                ('move_type', '=', 'out_invoice'),
            ]) - payments.sale_invoice_id  # invoice yang sudah dibayar payment ber-MOU tidak dihitung dua kali
            nilai_field, date_field, due_field = self._STAGE_SETUP_FIELDS[stage]
            vals = {nilai_field: sum(payments.mapped('amount')) + sum(legacy_invoices.mapped('amount_untaxed'))}

            dates = payments.mapped('date')
            if dates:
                vals[date_field] = max(dates)
            elif not legacy_invoices.filtered(lambda inv: inv.payment_state in ('in_payment', 'paid')):
                vals[date_field] = False

            due_dates = [
                due for due in payments.sale_invoice_id.mapped('invoice_date_due') if due
            ]
            if due_dates:
                vals[due_field] = min(due_dates)

            setup = self.env['account.move'].sudo()._get_or_create_setup(mou.id, stage)
            setup.write(vals)

    def action_post(self):
        self._check_mou_payment()
        res = super().action_post()
        self._reconcile_with_sale_order()
        self._sync_mou_tracking()
        return res

    def action_draft(self):
        so_payments = self.filtered(lambda pay: pay.timeline_stage in self._STAGES_WITH_SO)
        so_payments.move_id.line_ids.remove_move_reconcile()
        res = super().action_draft()
        self._sync_mou_tracking()
        return res

    def action_cancel(self):
        res = super().action_cancel()
        self._sync_mou_tracking()
        return res