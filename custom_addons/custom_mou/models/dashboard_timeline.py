from odoo import models, fields, api


class DashboardTimeline(models.Model):
    _name = 'dashboard.timeline.mou'
    _description = 'Timeline Progress MOU'

    # ─── Format Label Status ────────────────────────────────────────────────

    def _format_reg_status(self, model_type, status):
        """
        Format label status berdasarkan tipe model registrasi.
        Tiap model punya state berbeda — tidak bisa digabung satu mapping.
        """
        mapping = {
            'brand': {
                'draft': 'Draft',
                'sub_company_activation': 'Aktivasi Sub-Company',
                'regulatory_submit': 'Submit ke Regulatory',
                'bpom_verification': 'Verifikasi BPOM',
                'approved': 'Disetujui BPOM',
                'rejected': 'Ditolak',
            },
            'nie': {
                'draft': 'Draft',
                'form_request': 'Form Request (Approval)',
                'ro_drafting': 'RO Drafting',
                'submitted': 'Diajukan ke BPOM',
                'payment_request': 'Permintaan Pembayaran',
                'payment_verification': 'Verifikasi Pembayaran',
                'bpom_review': 'Review BPOM',
                'nie_issued': 'NIE Terbit',
                'failed': 'Gagal',
            },
            'halal': {
                'draft': 'Draft',
                'pengajuan': 'Pengajuan Dokumen',
                'verifikasi_internal': 'Verifikasi Internal',
                'submitted_lembaga': 'Diajukan ke Lembaga',
                'audit_halal': 'Audit Halal',
                'menunggu_keputusan': 'Menunggu Keputusan',
                'sertifikat_terbit': 'Sertifikat Terbit',
                'ditolak': 'Ditolak',
                'kadaluarsa': 'Kadaluarsa',
            },
        }
        return mapping.get(model_type, {}).get(status, status)

    # ─── Ambil Detail Registrasi (untuk accordion sub-data) ────────────────

    def _get_registrasi_data(self, mou_id):
        """
        Ambil detail tiap item registrasi per MOU.
        Dipakai untuk menampilkan accordion brand / NIE / halal di stage 4.
        Progress summary (count, done, progress%) diambil dari mou.container.
        """
        result = {'brand': [], 'nie': [], 'halal': []}

        # ── Brand ─────────────────────────────────────────────────────────
        brand_records = self.env['registrasi.brand'].search(
            [('mou_id', '=', mou_id)]
        )
        for rec in brand_records:
            nie_terbit = rec.produk_ids.mapped(
                'product_line_ids'
            ).filtered(
                lambda line: line.nie_number
                             and line.nie_issued_date
            )
            nie_issued_date = (
                nie_terbit[0].nie_issued_date
                if nie_terbit
                else None
            )
            nie_expired_date = (
                nie_terbit[0].nie_expired_date
                if nie_terbit
                else None
            )

            result['brand'].append({
                'id': rec.id,
                'name': rec.name,
                'brand': rec.brand_name,
                'owner': rec.brand_owner or '-',
                'status': rec.state,
                'status_label': self._format_reg_status('brand', rec.state),
                'tgl': None,
                'tgl_terbit': fields.Date.to_string(nie_issued_date)  if nie_issued_date  else None,
                'masa_berakhir': fields.Date.to_string(nie_expired_date) if nie_expired_date else None,
                'is_done': rec.state == 'approved',
                'has_attachment': bool(rec.doc_license_agreement or rec.doc_haki_certificate),
                'produk_count': rec.produk_count,
                'account_option': rec.account_option or '-',
            })

        # ── NIE / Produk ──────────────────────────────────────────────────
        nie_records = self.env['registrasi.produk'].search([
            '|',
            ('mou_id', '=', mou_id),
            ('brand_registration_id.mou_id', '=', mou_id),
        ])
        nie_records = nie_records._origin if hasattr(nie_records, '_origin') else nie_records
        seen_ids = set()
        for rec in nie_records:
            if rec.id in seen_ids:
                continue
            seen_ids.add(rec.id)

            for line in rec.product_line_ids:
                result['nie'].append({
                    'id': rec.id,
                    'name': rec.name,
                    'brand': (
                        rec.brand_registration_id.brand_name
                        if rec.brand_registration_id
                        else '-'
                    ),
                    # ambil dari line
                    'product_name': (
                        line.product_template_id.display_name
                        if line.product_template_id
                        else '-'
                    ),
                    'official_name': (
                            line.official_product_name
                            or '-'
                    ),
                    'status': rec.state,
                    'status_label': self._format_reg_status(
                        'nie',
                        rec.state
                    ),
                    'tgl': (
                        fields.Date.to_string(rec.submit_deadline)
                        if rec.submit_deadline
                        else None
                    ),
                    # NIE sekarang milik product line
                    'tgl_terbit': (
                        fields.Date.to_string(line.nie_issued_date)
                        if line.nie_issued_date
                        else None
                    ),
                    'masa_berakhir': (
                        fields.Date.to_string(line.nie_expired_date)
                        if line.nie_expired_date
                        else None
                    ),
                    'nie_number': (
                            line.nie_number
                            or '-'
                    ),
                    'is_done': (
                            rec.state == 'nie_issued'
                            and bool(line.nie_number)
                    ),
                    'has_attachment': bool(
                        rec.doc_pnbp
                        or rec.halal_cert_attachment
                    ),
                    'category': rec.category or '-',
                })

        # ── Halal ─────────────────────────────────────────────────────────
        halal_records = self.env['halal.registrasi'].search(
            [('mou_id', '=', mou_id)]
        )
        for rec in halal_records:
            result['halal'].append({
                'id': rec.id,
                'name': rec.name,
                'brand': rec.brand_registration_id.brand_name if rec.brand_registration_id else '-',
                'product_name': rec.product_name,
                'status': rec.state,
                'status_label': self._format_reg_status('halal', rec.state),
                'tgl': fields.Date.to_string(rec.tanggal_pengajuan) if rec.tanggal_pengajuan else None,
                'tgl_terbit': fields.Date.to_string(rec.tanggal_terbit)  if rec.tanggal_terbit  else None,
                'masa_berakhir': fields.Date.to_string(rec.tanggal_expired) if rec.tanggal_expired else None,
                'nomor_sertifikat': rec.nomor_sertifikat or '-',
                'is_done': rec.state == 'sertifikat_terbit',
                'has_attachment': bool(rec.doc_sertifikat_halal),
                'lembaga': rec.lembaga_sertifikasi or '-',
                'is_expired': rec.is_expired,
                'sisa_hari': rec.sisa_hari,
            })

        return result
    
    # ─── Ambil Detail Delivery + Retur (Pengiriman ke Customer) ─────────────

    def _get_delivery_data(self, mou_id):
        """
        Ambil detail pengiriman (stock.picking outgoing) DAN retur (incoming
        hasil wizard Return) untuk MOU ini.
        Stage 9 — Delivery: barang jadi dikirim ke customer, bisa saja diretur.
        """
        result = {'picking': [], 'retur': []}

        # ── Delivery Order (outgoing) ────────────────────────────────────
        pickings = self.env['stock.picking'].search([
            ('mou_id', '=', mou_id),
            ('picking_type_id.code', '=', 'outgoing'),
        ])
        def sale_order_of(picking):
            order = getattr(picking, 'sale_id', False) or picking.move_ids.sale_line_id.order_id[:1]
            return order

        for picking in pickings:
            sale_order = sale_order_of(picking)
            lines = []
            # Delivery dari SO tidak punya tab Deliveries, jadi pakai baris Operations.
            for line in picking.delivery_line_ids or picking.move_ids:
                is_move = line._name == 'stock.move'
                uom = line.product_uom if is_move else line.uom_id
                lines.append({
                    'product': line.product_id.name,
                    'qty': line.product_uom_qty if is_move else line.product_qty,
                    'uom': uom.name if uom else '-',
                    'jenis_product': dict(line._fields['jenis_product'].selection).get(line.jenis_product, '-') if line.jenis_product else '-',
                    'kemasan': dict(line._fields['kemasan'].selection).get(line.kemasan, '-') if line.kemasan else '-',
                    'ukuran': line.ukuran or '-',
                    'date_estimasi': fields.Date.to_string(line.date_estimasi) if line.date_estimasi else None,
                })

            result['picking'].append({
                'id': picking.id,
                'name': picking.name,
                'sale_order_id': sale_order.id or False,
                'sale_order_name': sale_order.display_name or False,
                'state': picking.state,
                'state_label': dict(picking._fields['state'].selection).get(picking.state, picking.state),
                'is_done': picking.state == 'done',
                'scheduled_date': fields.Date.to_string(picking.scheduled_date.date()) if picking.scheduled_date else None,
                'date_done': fields.Date.to_string(picking.date_done.date()) if picking.date_done else None,
                'lines': lines,
            })

        # ── Retur (incoming, hasil wizard Return dari delivery di atas) ──
        returns = self.env['stock.picking'].search([
            ('mou_id', '=', mou_id),
            ('picking_type_id.code', '=', 'incoming'),
            ('is_return', '=', True),
        ])
        for ret in returns:
            origin_picking = ret.move_ids.mapped('origin_returned_move_id.picking_id')
            sale_order = sale_order_of(origin_picking[:1]) if origin_picking else sale_order_of(ret)
            lines = []
            for move in ret.move_ids:
                lines.append({
                    'product': move.product_id.name,
                    'qty': move.product_uom_qty,
                    'uom': move.product_uom.name if move.product_uom else '-',
                })

            result['retur'].append({
                'id': ret.id,
                'name': ret.name,
                'sale_order_id': sale_order.id or False,
                'sale_order_name': sale_order.display_name or False,
                'state': ret.state,
                'state_label': dict(ret._fields['state'].selection).get(ret.state, ret.state),
                'is_done': ret.state == 'done',
                'date_done': fields.Date.to_string(ret.date_done.date()) if ret.date_done else None,
                'scheduled_date': fields.Date.to_string(ret.scheduled_date.date()) if ret.scheduled_date else None,
                'origin_picking': origin_picking[0].name if origin_picking else '-',
                'lines': lines,
            })

        # ── Ringkasan: terkirim (DO selesai dikurangi retur selesai) dibanding total MOU ──
        def done_qty(records):
            return sum(records.filtered(lambda p: p.state == 'done').move_ids.mapped('quantity'))

        # Terkirim per SO: DO selesai dikurangi retur selesai (retur ikut SO dari DO asalnya).
        by_so = {}
        for picking in pickings.filtered(lambda p: p.state == 'done'):
            so = sale_order_of(picking)
            if so:
                by_so[so.id] = by_so.get(so.id, 0.0) + sum(picking.move_ids.mapped('quantity'))
        for ret in returns.filtered(lambda p: p.state == 'done'):
            origin = ret.move_ids.mapped('origin_returned_move_id.picking_id')
            so = sale_order_of(origin[:1]) if origin else sale_order_of(ret)
            if so:
                by_so[so.id] = by_so.get(so.id, 0.0) - sum(ret.move_ids.mapped('quantity'))

        result['summary'] = {
            'delivered': done_qty(pickings) - done_qty(returns),
            'total': sum(self.env['draft.maklon'].browse(mou_id).maklon_line_ids.mapped('product_qty')),
            'by_so': {str(so_id): qty for so_id, qty in by_so.items()},
        }
        return result
    
    # ─── Ambil Data Sales Order (termasuk Repeat Order) ─────────────────────

    def _get_usulan_dana_data(self, mou, pr_records):
        """Usulan Dana untuk pembelian MOU ini: lewat PO, baris usulan, atau PR."""
        if 'usulan.usulan.dana' not in self.env:
            return []
        usulans = self.env['usulan.usulan.dana'].search([
            '|', '|', '|',
            ('purchase_order_id.mou_id', '=', mou.id),
            ('purchase_order_id.customer_line_ids.mou_id', '=', mou.id),
            ('line_ids.mou_id', '=', mou.id),
            ('id', 'in', pr_records.usulan_dana_id.ids),
            ('state', '!=', 'cancel'),
        ], order='tgl_usulan asc, id asc')
        state_labels = dict(usulans._fields['state'].selection)
        result = []
        for usulan in usulans:
            po = usulan.purchase_order_id
            request = pr_records.filtered(lambda pr: pr.usulan_dana_id == usulan)[:1]
            result.append({
                'id': usulan.id,
                'name': usulan.name,
                'state_label': state_labels.get(usulan.state, usulan.state),
                # Selesai = semua Plan Payment sudah dirilis.
                'is_done': usulan.status_payment == 'paid',
                'date': fields.Date.to_string(usulan.tgl_usulan) if usulan.tgl_usulan else None,
                'amount_total': usulan.amount_total,
                'po_name': po.name or False,
                'sale_order_id': po.sale_order_id.id or request.sale_order_id.id or False,
            })
        return result

    def _get_sale_order_data(self, mou_id):
        """Ambil SO aktif untuk MOU ini (termasuk Repeat Order), untuk dropdown filter."""
        stage_label_map = {
            'reg': 'Biaya Registrasi', 'dp': 'Down Payment',
            'nie': 'Tagihan NIE', 'peng': 'Pengadaan', 'bp': 'Balance Payment',
        }
        orders = self.env['sale.order'].search(
            [('mou_id', '=', mou_id), ('state', 'not in', ('draft', 'cancel'))], order='create_date asc'
        )
        result = []
        for so in orders:
            paid_invoice = so.invoice_ids.filtered(
                lambda inv: inv.state == 'posted'
                and inv.payment_state in ('paid', 'in_payment')
            )
            result.append({
                'id': so.id,
                'name': so.name,
                'timeline_stage_label': stage_label_map.get(so.timeline_stage, so.timeline_stage) or 'Seluruh Tahapan',
                'is_repeat_order': so.is_repeat_order,
                'is_paid': bool(paid_invoice),
                'amount_total': so.amount_total,
                'qty_total': sum(
                    line.product_uom_qty for line in so.order_line
                    if not line.display_type and line.product_id and line.product_id.type != 'service'
                ),
            })
        return result

    # ─── Dokumen tagihan per tahapan (untuk popup di tracking) ──────────────

    def _get_stage_docs(self, mou):
        """Customer Payment per tahapan, plus invoice lama yang masih bertahapan."""
        docs = {stage: [] for stage in ('reg', 'dp', 'nie', 'bp')}
        payments = self.env['account.payment'].search([
            ('mou_id', '=', mou.id),
            ('timeline_stage', '!=', False),
            ('state', 'not in', ('canceled', 'rejected')),
        ], order='date asc, id asc')
        for payment in payments:
            docs[payment.timeline_stage].append({
                'model': 'account.payment',
                'id': payment.id,
                'name': payment.display_name,
            })
        invoices = self.env['account.move'].search([
            ('mou_id', '=', mou.id),
            ('timeline_stage', '!=', False),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
        ], order='invoice_date asc, id asc')
        for invoice in invoices:
            docs[invoice.timeline_stage].append({
                'model': 'account.move',
                'id': invoice.id,
                'name': invoice.display_name,
            })
        return docs

    # ─── Hook: Progress Produksi (di-override oleh custom_production_planning) ──

    def _get_production_data(self, mou_id):
        """
        Placeholder.
        Modul custom_production_planning akan meng-override method ini
        lewat _inherit = 'dashboard.timeline.mou' untuk mengisi data asli.
        """
        return []

    # ─── Hook: Progress QC (di-override oleh custom_production_qc) ──────────

    def _get_qc_data(self, mou_id):
        """
        Placeholder.
        Modul custom_production_qc akan meng-override method ini
        lewat _inherit = 'dashboard.timeline.mou' untuk mengisi data asli.
        """
        return []

    # ─── Main Method ────────────────────────────────────────────────────────

    @api.model
    def get_timeline_data(self):
        mous = self.env['draft.maklon'].search([('state', '=', 'mou')])
        timeline_list = []

        for mou in mous:
            pelanggan_name = 'Unknown Customer'
            if mou.nama_cust:
                pelanggan_name = (
                    mou.nama_cust.name
                    if hasattr(mou.nama_cust, 'name')
                    else mou.nama_cust
                )

            container = self.env['mou.container'].search(
                [('mou_id', '=', mou.id)], limit=1
            )

            setups = self.env['mou.setup'].search([('mou_id', '=', mou.id)])
            setup_data = []
            for setup in setups:
                setup_data.append({
                    'id': setup.id,
                    'name': setup.name,
                    'state': setup.state,
                    'is_free': setup.is_free,
                    'reg_due_date':     fields.Date.to_string(setup.reg_due_date),
                    'reg_payment_date': fields.Date.to_string(setup.reg_payment_date),
                    'reg_nilai':        setup.reg_nilai,
                    'dp_due_date':      fields.Date.to_string(setup.dp_due_date),
                    'dp_payment_date':  fields.Date.to_string(setup.dp_payment_date),
                    'dp_nilai':         setup.dp_nilai,
                    'nie_due_date':     fields.Date.to_string(setup.nie_due_date),
                    'nie_payment_date': fields.Date.to_string(setup.nie_payment_date),
                    'nie_nilai':        setup.nie_nilai,
                    'peng_due_date':    fields.Date.to_string(setup.peng_due_date),
                    'peng_payment_date':fields.Date.to_string(setup.peng_payment_date),
                    'peng_nilai':       setup.peng_nilai,
                    'bp_due_date':      fields.Date.to_string(setup.bp_due_date),
                    'bp_payment_date':  fields.Date.to_string(setup.bp_payment_date),
                    'bp_nilai':         setup.bp_nilai,
                })

            registrasi_data = self._get_registrasi_data(mou.id)

            container_data = {}
            if container:
                container_data = {
                    'reg_due_date':    fields.Date.to_string(container.reg_due_date),
                    'reg_actual_date': fields.Date.to_string(container.reg_actual_date),
                    'reg_nilai':       container.reg_nilai,
                    'dp_due_date':    fields.Date.to_string(container.dp_due_date),
                    'dp_actual_date': fields.Date.to_string(container.dp_actual_date),
                    'dp_nilai':       container.dp_nilai,
                    'nie_due_date':    fields.Date.to_string(container.nie_due_date),
                    'nie_actual_date': fields.Date.to_string(container.nie_actual_date),
                    'nie_nilai':       container.nie_nilai,
                    'nie_count':    container.nie_count,
                    'nie_done':     container.nie_done,
                    'nie_progress': container.nie_progress,
                    'halal_count':    container.halal_count,
                    'halal_done':     container.halal_done,
                    'halal_progress': container.halal_progress,
                    'brand_count':    container.brand_count,
                    'brand_done':     container.brand_done,
                    'brand_progress': container.brand_progress,
                    'peng_due_date':    fields.Date.to_string(container.peng_due_date),
                    'peng_actual_date': fields.Date.to_string(container.peng_actual_date),
                    'peng_nilai':       container.peng_nilai,
                    'bp_due_date':    fields.Date.to_string(container.bp_due_date),
                    'bp_actual_date': fields.Date.to_string(container.bp_actual_date),
                    'bp_nilai':       container.bp_nilai,
                }

            # ── PR Data — di dalam loop mou ──────────────────────────────
            pr_records = self.env['purchase.request'].search([
                '|',
                ('mou_id', '=', mou.id),
                ('bulk_line_ids.mou_id', '=', mou.id),
            ])
            pr_data = []
            for pr in pr_records:
                # Cari PO terkait PR ini (relasi langsung, lalu via origin)
                po = self.env['purchase.order'].search([
                    ('purchase_request_id', '=', pr.id),
                ], limit=1) or self.env['purchase.order'].search([
                    ('customer_line_ids.request_id', '=', pr.id),
                ], limit=1) or self.env['purchase.order'].search([
                    ('origin', 'like', pr.name),
                ], limit=1)

                # Tentukan state PR yang sudah di-submit
                pr_is_done = pr.state == 'pr'

                # Stock picking terkait PO (receipt/done)
                delivered = False
                picking_id = None
                picking_name = None
                picking_date = None
                # =====================================================
                # BULK PURCHASE
                # =====================================================
                if pr.is_bulk_purchase:

                    bulk_lines = pr.bulk_line_ids.filtered(
                        lambda l: l.mou_id.id == mou.id
                    )

                    products = bulk_lines.mapped('product_id.name')
                    product_summary = ', '.join(products) if products else '-'

                    amount = sum(bulk_lines.mapped('price_subtotal'))

                    bulk_allocations = [{
                        'mou_id': line.mou_id.id,
                        'mou_name': line.mou_id.draft_name,
                        'customer': line.customer_id.name,
                        'product': line.product_id.name,
                        'qty': line.qty,
                        'uom': line.uom_id.name,
                        'price_unit': line.price_unit,
                        'subtotal': line.price_subtotal,
                    } for line in bulk_lines]

                    # ==========================
                    # CEK RECEIPT BULK
                    # ==========================
                    if po:

                        pickings = self.env['stock.picking'].search([
                            ('purchase_id', '=', po.id),
                            ('state', '=', 'done'),
                        ])

                        bulk_products = bulk_lines.mapped('product_id')

                        for pick in pickings:

                            received_products = pick.move_ids.mapped('product_id')

                            # cukup salah satu produk bulk milik MOU ini diterima
                            if any(prod in received_products for prod in bulk_products):
                                delivered = True
                                picking_id = pick.id
                                picking_name = pick.name
                                picking_date = fields.Date.to_string(
                                    pick.date_done.date() if pick.date_done else None
                                )
                                break

                # =====================================================
                # PR BIASA
                # =====================================================
                else:

                    products = pr.request_line_ids.mapped('product_id.name')
                    product_summary = ', '.join(products) if products else '-'

                    amount = pr.total_amount
                    bulk_allocations = []

                    if po:

                        picking = self.env['stock.picking'].search([
                            ('purchase_id', '=', po.id),
                            ('state', '=', 'done'),
                        ], limit=1)

                        if picking:
                            delivered = True
                            picking_id = picking.id
                            picking_name = picking.name
                            picking_date = fields.Date.to_string(
                                picking.date_done.date() if picking.date_done else None
                            )

                # =====================================================
                # Append
                # =====================================================
                pr_data.append({
                    'id': pr.id,
                    'name': pr.name,
                    'sale_order_id': pr.sale_order_id.id or False,
                    'po_sale_order_id': (po.sale_order_id.id or pr.sale_order_id.id or False) if po else False,
                    'state': pr.state,
                    'state_label': dict(pr._fields['state'].selection).get(
                        pr.state, pr.state
                    ),
                    'purchase_type': 'bulk' if pr.is_bulk_purchase else 'normal',
                    'date_usulan': fields.Date.to_string(pr.date_usulan)
                    if pr.date_usulan else None,
                    'product_summary': product_summary,
                    'bulk_allocations': bulk_allocations,
                    'total_amount': amount,
                    'is_urgent': pr.is_urgent,
                    'pr_is_done': pr_is_done,

                    # PO
                    'po_id': po.id if po else None,
                    'po_name': po.name if po else None,
                    'po_date': fields.Date.to_string(po.date_order.date())
                    if po and po.date_order else None,
                    'po_state': po.state if po else None,
                    'po_is_done': po.state in ('purchase', 'done') if po else False,

                    # Delivered
                    'delivered': delivered,
                    'delivered_id': picking_id,
                    'delivered_name': picking_name,
                    'delivered_date': picking_date,
                })

            delivery_data = self._get_delivery_data(mou.id)
            sale_order_data = self._get_sale_order_data(mou.id)
            production_data = self._get_production_data(mou.id)
            qc_data = self._get_qc_data(mou.id)

            timeline_list.append({
                'id': mou.id,
                'pelanggan': pelanggan_name,
                'no_mou': mou.draft_name or '-',
                'tgl_draft': (
                    fields.Date.to_string(mou.tgl_draft)
                    if mou.tgl_draft
                    else fields.Date.to_string(fields.Date.today())
                ),
                'setups': setup_data,
                'container': container_data,
                'registrasi': registrasi_data,
                'pr_data': pr_data,
                'usulan_data': self._get_usulan_dana_data(mou, pr_records),
                'stage_docs': self._get_stage_docs(mou),
                'delivery_data': delivery_data,
                'sale_orders': sale_order_data,
                'production_data': production_data,
                'qc_data': qc_data,
            })

        return timeline_list