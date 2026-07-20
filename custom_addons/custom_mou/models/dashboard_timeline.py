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
        for picking in pickings:
            lines = []
            for line in picking.delivery_line_ids:
                lines.append({
                    'product': line.product_id.name,
                    'qty': line.product_qty,
                    'uom': line.uom_id.name if line.uom_id else '-',
                    'jenis_product': dict(line._fields['jenis_product'].selection).get(line.jenis_product, '-') if line.jenis_product else '-',
                    'kemasan': dict(line._fields['kemasan'].selection).get(line.kemasan, '-') if line.kemasan else '-',
                    'ukuran': line.ukuran or '-',
                    'date_estimasi': fields.Date.to_string(line.date_estimasi) if line.date_estimasi else None,
                })

            result['picking'].append({
                'id': picking.id,
                'name': picking.name,
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
                'state': ret.state,
                'state_label': dict(ret._fields['state'].selection).get(ret.state, ret.state),
                'is_done': ret.state == 'done',
                'date_done': fields.Date.to_string(ret.date_done.date()) if ret.date_done else None,
                'scheduled_date': fields.Date.to_string(ret.scheduled_date.date()) if ret.scheduled_date else None,
                'origin_picking': origin_picking[0].name if origin_picking else '-',
                'lines': lines,
            })

        return result
    
    # ─── Ambil Data Sales Order (termasuk Repeat Order) ─────────────────────

    def _get_sale_order_data(self, mou_id):
        """Ambil semua SO untuk MOU ini (termasuk Repeat Order), untuk dropdown filter."""
        stage_label_map = {
            'reg': 'Biaya Registrasi', 'dp': 'Down Payment',
            'nie': 'Tagihan NIE', 'peng': 'Pengadaan', 'bp': 'Balance Payment',
        }
        orders = self.env['sale.order'].search(
            [('mou_id', '=', mou_id)], order='create_date asc'
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
                'timeline_stage_label': stage_label_map.get(so.timeline_stage, so.timeline_stage),
                'is_repeat_order': so.is_repeat_order,
                'is_paid': bool(paid_invoice),
                'amount_total': so.amount_total,
            })
        return result

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
            pr_records = self.env['purchase.request'].search(
                [('mou_id', '=', mou.id)]
            )
            pr_data = []
            for pr in pr_records:
                # Cari PO terkait PR ini (via origin)
                po = self.env['purchase.order'].search([
                    ('origin', 'like', pr.name),
                    ('mou_id', '=', mou.id),
                ], limit=1)

                # Fallback: cari PO langsung via mou_id jika origin tidak cocok
                if not po:
                    po = self.env['purchase.order'].search([
                        ('mou_id', '=', mou.id),
                    ], limit=1)

                # Stock picking terkait PO (receipt/done)
                picking = None
                picking_date = None
                picking_name = None
                if po:
                    picking = self.env['stock.picking'].search([
                        ('purchase_id', '=', po.id),
                        ('state', '=', 'done'),
                    ], limit=1)
                    if picking:
                        picking_name = picking.name
                        picking_date = fields.Date.to_string(
                            picking.date_done.date() if picking.date_done else None
                        )

                # Tentukan state PR yang sudah di-submit
                pr_is_done = pr.state == 'pr'

                pr_data.append({
                    'id': pr.id,
                    'name': pr.name,
                    'state': pr.state,
                    'state_label': dict(pr._fields['state'].selection).get(pr.state, pr.state),
                    'date_usulan': fields.Date.to_string(pr.date_usulan) if pr.date_usulan else None,
                    'product_summary': pr.product_summary or '-',
                    'total_amount': pr.total_amount,
                    'is_urgent': pr.is_urgent,
                    'pr_is_done': pr_is_done,
                    # PO
                    'po_id': po.id if po else None,
                    'po_name': po.name if po else None,
                    'po_date': fields.Date.to_string(po.date_order.date()) if po and po.date_order else None,
                    'po_state': po.state if po else None,
                    'po_is_done': po.state in ('purchase', 'done') if po else False,
                    # Delivered
                    'delivered': bool(picking),
                    'delivered_name': picking_name,
                    'delivered_date': picking_date,
                })

            delivery_data = self._get_delivery_data(mou.id)
            sale_order_data = self._get_sale_order_data(mou.id)

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
                'delivery_data': delivery_data,
                'sale_orders': sale_order_data,
            })

        return timeline_list