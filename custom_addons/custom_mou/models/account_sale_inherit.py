from odoo import models, fields, api


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
        ('peng', 'Pengadaan'),
        ('bp' , 'Balance Payment'),
    ], string='Tahapan', default='reg', required=True)

    is_repeat_order = fields.Boolean(
        string='Repeat Order?',
        default=False,
        copy=False,
    )

    bp_total_kontrak = fields.Monetary(
        string='Total Nilai Kontrak', compute='_compute_bp_outstanding')
    bp_total_tertagih = fields.Monetary(
        string='Sudah Ditagih (Semua Tahapan)', compute='_compute_bp_outstanding')
    bp_outstanding_amount = fields.Monetary(
        string='Sisa Tunggakan', compute='_compute_bp_outstanding')

    @api.depends('mou_id', 'timeline_stage')
    def _compute_bp_outstanding(self):
        for order in self:
            order.bp_total_kontrak = 0.0
            order.bp_total_tertagih = 0.0
            order.bp_outstanding_amount = 0.0

            if order.timeline_stage != 'bp' or not order.mou_id:
                continue

            dp_invoices = self.env['account.move'].search([
                ('mou_id', '=', order.mou_id.id),
                ('state', '=', 'posted'),
                ('move_type', 'in', ('out_invoice', 'out_refund')),
                ('timeline_stage', '=', 'dp'),
            ])

            total_dp = sum(
                inv.amount_total if inv.move_type == 'out_invoice'
                else -inv.amount_total
                for inv in dp_invoices
            )

            order.bp_total_kontrak = order.mou_id.nilai_kontrak or 0.0
            order.bp_total_tertagih = total_dp
            order.bp_outstanding_amount = (
                    order.bp_total_kontrak - total_dp
            )
    
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
    
    @api.onchange('mou_id', 'timeline_stage')
    def _onchange_mou_id_fill_lines(self):
        """
        Saat No. MOU dipilih (atau tahapan diganti), isi order_line otomatis
        dari data draft.maklon.maklon_line_ids.

        - Untuk tahapan 'bp' (Balance Payment): hitung proporsional dari SISA
        tunggakan kontrak (logic lama, dipertahankan).
        - Untuk tahapan lain (reg, dp, nie, peng): isi langsung dari HNA per
        baris produk MOU (tanpa proporsi sisa tunggakan).
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
        # TAHAPAN LAIN (reg, dp, nie, peng): isi langsung dari HNA per baris
        # ═══════════════════════════════════════════════════════════════
        stage_label_map = {
            'reg':  'Biaya Registrasi',
            'dp':   'Down Payment',
            'nie':  'Tagihan NIE',
            'peng': 'Pengadaan',
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
        ('peng', 'Pengadaan'),
        ('bp', 'Balance Payment'),
    ], string='Tahapan', readonly=False, copy=False)

    # ── Mapping timeline_stage invoice → state mou.setup ─────────────────────
    # timeline_stage di invoice pakai 'reg','dp','nie','peng'
    # state di mou.setup pakai 'biaya_registrasi','dp','nie','pengadaan'
    _STAGE_TO_SETUP_STATE = {
        'reg':  'biaya_registrasi',
        'dp':   'dp',
        'nie':  'nie',
        'peng': 'pengadaan',
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
            'peng': 'peng_due_date',
            'bp' : 'bp_due_date',
        }
        nilai_field_map = {
            'reg':  'reg_nilai',
            'dp':   'dp_nilai',
            'nie':  'nie_nilai',
            'peng': 'peng_nilai',
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
            'peng': 'peng_payment_date',
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
        domain=[('state', '=', 'mou')]
    )