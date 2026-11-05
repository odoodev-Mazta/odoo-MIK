import re
from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    customer_id = fields.Many2one(
        'res.partner',
        string='Customer'
    )

    mou_id = fields.Many2one(
        'draft.maklon',
        string='No. MOU',
        domain="[('nama_cust','=',customer_id), ('state','=','mou')]"
    )

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        domain="[('mou_id', '=', mou_id)]"
    )

    purchase_request_id = fields.Many2one(
        'purchase.request',
        string='No. PR',
        copy=False,
        domain="[('state', '=', 'pr'), ('company_id', '=', company_id)]"
    )

    recommended_vendor_ids = fields.Many2many(
        'res.partner',
        string='Vendor Rekomendasi PR',
        compute='_compute_recommended_vendors',
    )

    recommended_vendor_note = fields.Char(
        string='Belum Terdaftar',
        compute='_compute_recommended_vendors',
    )

    recommended_vendor_id = fields.Many2one(
        'res.partner',
        string='Rekomendasi Vendor',
        compute='_compute_recommended_vendor_id',
        inverse='_inverse_recommended_vendor_id',
        domain="[('id', 'in', recommended_vendor_ids)]",
    )

    item_line_ids = fields.One2many(
        'purchase.order.line',
        'order_id',
        string='Item Barang'
    )

    setup_line_ids = fields.One2many(
        'purchase.order.setup.line',
        'order_id',
        string='Item Setup'
    )

    customer_line_ids = fields.One2many(
        'purchase.order.customer.line',
        'order_id',
        string='Customer PR',
        copy=True,
    )

    purchase_request_ids = fields.Many2many(
        'purchase.request',
        string='Semua PR dalam PO',
        compute='_compute_purchase_request_ids',
        inverse='_inverse_purchase_request_ids',
    )

    def _remove_requests(self, requests):
        """Batalkan PR dari PO ini: kurangi qty barangnya, hapus rinciannya, PR bebas dipakai lagi."""
        for order in self:
            lines = order.customer_line_ids.filtered(lambda l: l.request_id in requests)
            for line in lines:
                for order_line in order.order_line.filtered(
                    lambda l: not l.display_type and l.product_id == line.product_id
                    and (not line.uom_id or l.product_uom_id == line.uom_id)
                )[:1]:
                    remaining = order_line.product_qty - line.qty
                    if remaining > 1e-9:
                        order_line.product_qty = remaining
                    else:
                        order.order_line -= order_line
            order.customer_line_ids -= lines
            order.setup_line_ids -= order.setup_line_ids.filtered(lambda l: l.request_id in requests)
            left = order.customer_line_ids.request_id
            order.purchase_request_id = left[:1]
            order.origin = ', '.join(left.mapped('name')) or False
            if order.customer_line_ids:
                order._sync_header_from_customer_lines()
            else:
                order.mou_id = order.customer_id = order.sale_order_id = False

    @api.onchange('purchase_request_ids')
    def _onchange_purchase_request_ids(self):
        """Tombol X pada PR di bagian atas: PR itu dikeluarkan dari PO."""
        removed = self.customer_line_ids.request_id - self.purchase_request_ids
        if removed:
            self._remove_requests(removed)

    def _inverse_purchase_request_ids(self):
        for order in self:
            removed = order.customer_line_ids.request_id - order.purchase_request_ids
            if removed:
                order._remove_requests(removed)

    @api.depends('purchase_request_id', 'customer_line_ids.request_id')
    def _compute_purchase_request_ids(self):
        for order in self:
            order.purchase_request_ids = order.purchase_request_id | order.customer_line_ids.request_id

    merged_into_id = fields.Many2one('purchase.order', string='Digabung ke', copy=False, readonly=True, index=True)
    merged_from_ids = fields.One2many('purchase.order', 'merged_into_id', string='Hasil gabungan dari')

    customer_line_warning = fields.Text(compute='_compute_customer_line_warning')

    customer_line_stock_note = fields.Text(compute='_compute_customer_line_warning')

    @api.depends('customer_line_ids.qty', 'customer_line_ids.product_id',
                 'order_line.product_qty', 'order_line.product_id')
    def _compute_customer_line_warning(self):
        for order in self:
            order.customer_line_warning = False
            order.customer_line_stock_note = False
            if not order.customer_line_ids:
                continue
            ordered = defaultdict(float)
            allocated = defaultdict(float)
            for line in order.order_line:
                if not line.display_type and line.product_id:
                    ordered[line.product_id] += line.product_qty
            for line in order.customer_line_ids:
                allocated[line.product_id] += line.qty
            over, rest = [], []
            for product in (ordered.keys() | allocated.keys()):
                diff = ordered[product] - allocated[product]
                if diff < -1e-6:
                    over.append(f"{product.display_name}: qty PO {ordered[product]:g}, dialokasikan {allocated[product]:g}")
                elif diff > 1e-6:
                    rest.append(f"{product.display_name}: {diff:g} dari {ordered[product]:g}")
            order.customer_line_warning = "\n".join(over) or False
            order.customer_line_stock_note = "\n".join(rest) or False

    usulan_dana_ids = fields.One2many(
        'usulan.usulan.dana',
        'purchase_order_id',
        string='Usulan Dana',
    )

    usulan_dana_count = fields.Integer(
        compute='_compute_usulan_dana',
    )

    has_active_usulan_dana = fields.Boolean(
        compute='_compute_usulan_dana',
    )

    @api.depends('usulan_dana_ids.state')
    def _compute_usulan_dana(self):
        for order in self:
            order.usulan_dana_count = len(order.usulan_dana_ids)
            order.has_active_usulan_dana = bool(order.usulan_dana_ids.filtered(
                lambda ud: ud.state not in ('reject', 'cancel')
            ))

    def action_create_usulan_dana(self):
        """Buka form Usulan Dana baru; vendor & baris terisi dari onchange PO di Usulan Dana."""
        self.ensure_one()
        if self.state != 'purchase':
            raise UserError('Usulan Dana hanya bisa dibuat dari PO yang sudah dikonfirmasi.')
        if self.has_active_usulan_dana:
            raise UserError(f'PO {self.name} sudah punya Usulan Dana yang masih berjalan.')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Usulan Dana',
            'res_model': 'usulan.usulan.dana',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_document_type': 'ud',
                'default_purchase_order_id': self.id,
            },
        }

    def action_view_usulan_dana(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': 'Usulan Dana',
            'res_model': 'usulan.usulan.dana',
            'domain': [('purchase_order_id', '=', self.id)],
            'context': {'default_document_type': 'ud', 'default_purchase_order_id': self.id},
        }
        if self.usulan_dana_count == 1:
            action.update(view_mode='form', res_id=self.usulan_dana_ids.id)
        else:
            action['view_mode'] = 'list,form'
        return action

    @api.depends(
        'purchase_request_id.recommended_vendor_1',
        'purchase_request_id.recommended_vendor_2',
        'customer_line_ids.request_id.recommended_vendor_1',
        'customer_line_ids.request_id.recommended_vendor_2',
        'company_id',
    )
    def _compute_recommended_vendors(self):
        for order in self:
            vendors = self.env['res.partner']
            unregistered = []
            names = {
                name.strip()
                for request in order.purchase_request_ids
                for name in (request.recommended_vendor_1, request.recommended_vendor_2)
                if name and name.strip()
            }
            for name in sorted(names):
                partners = self.env['res.partner'].search([
                    ('name', '=ilike', name),
                    ('company_id', 'in', [False, order.company_id.id]),
                ])
                if partners:
                    vendors |= partners
                else:
                    unregistered.append(name)
            order.recommended_vendor_ids = vendors
            order.recommended_vendor_note = ', '.join(unregistered)

    @api.depends('partner_id', 'recommended_vendor_ids')
    def _compute_recommended_vendor_id(self):
        for order in self:
            order.recommended_vendor_id = (
                order.partner_id if order.partner_id in order.recommended_vendor_ids else False
            )

    def _inverse_recommended_vendor_id(self):
        for order in self:
            if order.recommended_vendor_id:
                order.partner_id = order.recommended_vendor_id

    @api.onchange('recommended_vendor_id')
    def _onchange_recommended_vendor(self):
        if self.recommended_vendor_id:
            self.partner_id = self.recommended_vendor_id

    def _fill_single_sale_order(self):
        """SO terisi otomatis hanya jika MOU punya tepat satu SO."""
        if self.sale_order_id or not self.mou_id:
            return
        orders = self.env['sale.order'].search([
            ('mou_id', '=', self.mou_id.id),
            ('company_id', '=', self.company_id.id),
            ('state', '!=', 'cancel'),
        ], limit=2)
        if len(orders) == 1:
            self.sale_order_id = orders

    @api.onchange('mou_id')
    def _onchange_mou(self):
        if self.mou_id:
            self.customer_id = self.mou_id.nama_cust
        if self.sale_order_id.mou_id != self.mou_id:
            self.sale_order_id = False
        self._fill_single_sale_order()

    @api.onchange('customer_id')
    def _onchange_customer(self):
        if self.mou_id.nama_cust != self.customer_id:
            self.mou_id = False

    def _prepare_request_lines(self, request):
        """Baris barang, item setup, dan rincian customer dari satu PR."""
        default_date = request.estimated_date or fields.Date.context_today(self)
        order_lines, setup_lines, customer_lines = [], [], []

        def customer_vals(product, qty, uom, mou=False, sale_order=False):
            return {
                'request_id': request.id,
                'mou_id': mou.id if mou else False,
                'customer_id': mou.nama_cust.id if mou else request.customer_id.id,
                'sale_order_id': sale_order.id if sale_order else False,
                'product_id': product.id,
                'qty': qty,
                'uom_id': uom.id,
            }

        for line in request.request_line_ids.filtered(lambda l: not l.display_type):
            if line.line_type == 'setup' and line.setup_item_id:
                setup_lines.append({
                    'request_id': request.id,
                    'setup_item_id': line.setup_item_id.id,
                    'description': line.description,
                    'item_qty': line.item_qty,
                })
            elif line.product_id:
                uom = line.product_uom or line.product_id.uom_id
                order_lines.append({
                    'product_id': line.product_id.id,
                    'name': line.description or line.product_id.display_name,
                    'product_qty': line.product_qty,
                    'product_uom_id': uom.id,
                    'price_unit': line.price_unit,
                    'date_planned': line.date_planned or default_date,
                    'tax_ids': [(6, 0, line.tax_ids.ids)],
                })
                customer_lines.append(customer_vals(
                    line.product_id, line.product_qty, uom, request.mou_id, request.sale_order_id))
        if request.is_bulk_purchase:
            for line in request.bulk_line_ids:
                order_lines.append({
                    'product_id': line.product_id.id,
                    'name': line.product_id.display_name,
                    'product_qty': line.qty,
                    'product_uom_id': line.uom_id.id,
                    'price_unit': line.price_unit,
                    'date_planned': default_date,
                })
                customer_lines.append(customer_vals(line.product_id, line.qty, line.uom_id, line.mou_id))
        return order_lines, setup_lines, customer_lines

    def _requests_from_origin(self):
        """PR yang namanya tertulis di kolom Origin (Merge bawaan Odoo menggabungkan Origin RFQ)."""
        self.ensure_one()
        names = [name for name in re.split(r'[,;\s]+', self.origin or '') if name]
        if not names:
            return self.env['purchase.request']
        return self.env['purchase.request'].search([('name', 'in', names)])

    def _fill_missing_requests(self):
        """Baris Customer PR tanpa No. PR: cari PR di Origin yang MOU-nya sama (hanya bila tepat satu)."""
        for order in self:
            missing = order.customer_line_ids.filtered(lambda l: not l.request_id)
            if not missing:
                continue
            origin_requests = order._requests_from_origin()
            for line in missing:
                candidates = origin_requests.filtered(lambda r: r.mou_id == line.mou_id) if line.mou_id else origin_requests
                if len(candidates) == 1:
                    line.request_id = candidates

    def _sync_header_from_customer_lines(self):
        """Bagian atas PO: satu MOU/customer bila semua baris sama; kosong bila beragam."""
        self._fill_missing_requests()
        for order in self:
            lines = order.customer_line_ids
            if not lines:
                continue
            mous = lines.mou_id
            sales = lines.sale_order_id
            requests = lines.request_id
            order.mou_id = mous if len(mous) == 1 else False
            order.customer_id = mous.nama_cust if len(mous) == 1 else False
            order.sale_order_id = sales if len(sales) == 1 and len(mous) == 1 else False
            if requests and order.purchase_request_id not in requests:
                order.purchase_request_id = requests[0]
            order.origin = ', '.join(requests.mapped('name')) or order.origin

    def _warning_requests_in_use(self, requests):
        """Teks peringatan bila PR sudah ada di RFQ/PO aktif lain (tidak memblokir)."""
        lines = []
        for request in requests:
            others = request._active_orders().filtered(lambda po: po._origin.id != self._origin.id)
            if others:
                lines.append(f'{request.name} sudah ada di {", ".join(others.mapped("name"))}')
        if not lines:
            return False
        return '\n'.join(lines) + '\nPastikan barangnya tidak dipesan dua kali.'

    def _autofill_vendor(self):
        """Vendor PO mengikuti kolom Vendor di Keterangan PR (tanpa memeriksa Vendor sudah terisi atau belum).

        Bila semua baris memilih vendor yang sama, itu menjadi Vendor PO. Bila belum ada pilihan dan PR
        hanya merekomendasikan satu vendor terdaftar, vendor itu dipakai.
        """
        for order in self:
            chosen = order.customer_line_ids.vendor_choice_id
            if len(chosen) == 1:
                order.partner_id = chosen
            elif not chosen and len(order.recommended_vendor_ids) == 1:
                order.partner_id = order.recommended_vendor_ids

    @api.onchange('customer_line_ids')
    def _onchange_customer_line_vendor(self):
        chosen = self.customer_line_ids.vendor_choice_id
        if len(chosen) == 1:
            self.partner_id = chosen

    def _add_requests(self, requests):
        """Tambahkan barang beberapa PR ke PO ini. Produk yang sama digabung, rinciannya tetap per customer."""
        self.ensure_one()
        for request in requests:
            order_lines, setup_lines, customer_lines = self._prepare_request_lines(request)
            for vals in order_lines:
                existing = self.order_line.filtered(
                    lambda l: not l.display_type and l.product_id.id == vals['product_id']
                    and l.product_uom_id.id == vals['product_uom_id']
                )[:1]
                if existing:
                    existing.product_qty += vals['product_qty']
                else:
                    self.write({'order_line': [(0, 0, vals)]})
            self.write({
                'setup_line_ids': [(0, 0, vals) for vals in setup_lines],
                'customer_line_ids': [(0, 0, vals) for vals in customer_lines],
            })
            if not self.currency_id or not self.order_line:
                self.currency_id = request.currency_id
        self._sync_header_from_customer_lines()
        self._autofill_vendor()

    def action_add_requests(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Ambil Barang dari PR',
            'res_model': 'purchase.order.add.request.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_order_id': self.id},
        }

    def action_merge(self):
        """Merge membuat RFQ BARU; RFQ asal tidak ditimpa dan bisa dikembalikan lewat Batalkan Merge."""
        rfqs = self.filtered(lambda r: r.state in ('draft', 'sent') and not r.merged_into_id)
        if len(rfqs) < 2:
            raise UserError('Pilih minimal dua RFQ (status RFQ atau RFQ Sent) yang belum digabung.')
        grouped = defaultdict(lambda: self.browse())
        for rfq in rfqs:
            grouped[self._prepare_grouped_data(rfq)] += rfq
        groups = [group for group in grouped.values() if len(group) > 1]
        if not groups:
            raise UserError(
                'RFQ yang digabung harus punya Vendor, mata uang, dan alamat tujuan yang sama.\n'
                'Catatan: dua kontak vendor yang namanya sama tetapi datanya berbeda dianggap vendor berbeda.'
            )
        merged = self.browse()
        for group in groups:
            merged |= self._merge_into_new(group)
        action = {
            'type': 'ir.actions.act_window',
            'name': 'RFQ Hasil Gabungan',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', merged.ids)],
        }
        if len(merged) == 1:
            action.update(view_mode='form', res_id=merged.id)
        return action

    def _merge_into_new(self, group):
        oldest = min(group, key=lambda r: r.date_order)
        group._ensure_customer_lines()
        new = self.create({
            'partner_id': oldest.partner_id.id,
            'currency_id': oldest.currency_id.id,
            'dest_address_id': oldest.dest_address_id.id,
            'company_id': oldest.company_id.id,
            'picking_type_id': oldest.picking_type_id.id,
            'payment_term_id': oldest.payment_term_id.id,
            'fiscal_position_id': oldest.fiscal_position_id.id,
            'origin': ', '.join(dict.fromkeys(filter(None, group.mapped('origin')))) or False,
            'partner_ref': ', '.join(dict.fromkeys(filter(None, group.mapped('partner_ref')))) or False,
        })
        for line in group.order_line.filtered(lambda l: not l.display_type and l.product_id):
            same = new.order_line.filtered(
                lambda l: l.product_id == line.product_id and l.product_uom_id == line.product_uom_id
                and l.price_unit == line.price_unit and l.discount == line.discount
            )[:1]
            if same:
                same.product_qty += line.product_qty
            else:
                self.env['purchase.order.line'].create(line.copy_data({'order_id': new.id})[0])
        new.write({
            'customer_line_ids': [(0, 0, {
                'request_id': c.request_id.id,
                'mou_id': c.mou_id.id,
                'customer_id': c.customer_id.id,
                'sale_order_id': c.sale_order_id.id,
                'product_id': c.product_id.id,
                'qty': c.qty,
                'uom_id': c.uom_id.id,
            }) for c in group.customer_line_ids],
            'setup_line_ids': [(0, 0, {
                'request_id': s.request_id.id,
                'setup_item_id': s.setup_item_id.id,
                'description': s.description,
                'item_qty': s.item_qty,
            }) for s in group.setup_line_ids],
        })
        new._sync_header_from_customer_lines()
        group.write({'merged_into_id': new.id})
        names = ', '.join(group.mapped('name'))
        new.message_post(body=f'RFQ ini hasil gabungan dari: {names}. Klik Batalkan Merge bila tidak jadi digabung.')
        for rfq in group:
            rfq.message_post(body=f'RFQ digabung ke {new.name}. Batalkan merge di {new.name} untuk mengaktifkannya kembali.')
        return new

    def _release_merge(self):
        """Batalkan merge: RFQ asal aktif kembali."""
        for order in self:
            originals = order.merged_from_ids
            if not originals:
                continue
            originals.write({'merged_into_id': False})
            for rfq in originals:
                rfq.message_post(body=f'Merge ke {order.name} dibatalkan. RFQ ini aktif kembali.')
            order.message_post(body='Merge dibatalkan. RFQ asal aktif kembali.')

    def action_undo_merge(self):
        self.ensure_one()
        return self.button_cancel()

    def button_cancel(self):
        if not self.env.context.get('skip_merge_release'):
            self.filtered('merged_from_ids')._release_merge()
        return super().button_cancel()

    def button_confirm(self):
        for order in self.filtered('merged_into_id'):
            raise UserError(
                f'{order.name} sudah digabung ke {order.merged_into_id.name}. '
                f'Konfirmasi {order.merged_into_id.name}, atau batalkan merge-nya lebih dulu.'
            )
        return super().button_confirm()

    def _ensure_customer_lines(self):
        """PO lama (sebelum ada tab Customer PR): bentuk rincian dari MOU/PR di bagian atas PO."""
        for order in self:
            if order.customer_line_ids or not (order.mou_id or order.purchase_request_id):
                continue
            quantities = defaultdict(float)
            uoms = {}
            for line in order.order_line.filtered(lambda l: not l.display_type and l.product_id):
                quantities[line.product_id] += line.product_qty
                uoms[line.product_id] = line.product_uom_id
            from_origin = order._requests_from_origin()
            from_origin = from_origin.filtered(lambda r: r.mou_id == order.mou_id) or from_origin
            request = order.purchase_request_id or (from_origin if len(from_origin) == 1 else from_origin[:0])
            order.customer_line_ids = [(0, 0, {
                'request_id': request.id,
                'mou_id': order.mou_id.id,
                'customer_id': order.customer_id.id or order.mou_id.nama_cust.id,
                'sale_order_id': order.sale_order_id.id,
                'product_id': product.id,
                'qty': qty,
                'uom_id': uoms[product].id,
            }) for product, qty in quantities.items()]

    @api.onchange('purchase_request_id')
    def _onchange_purchase_request(self):
        request = self.purchase_request_id
        if not request:
            return

        self.customer_id = request.customer_id
        self.mou_id = request.mou_id
        self.sale_order_id = request.sale_order_id
        self._fill_single_sale_order()
        self.currency_id = request.currency_id
        self.origin = request.name

        warning = self._warning_requests_in_use(request)
        order_lines, setup_lines, customer_lines = self._prepare_request_lines(request)
        self.order_line = [(5, 0, 0)] + [(0, 0, vals) for vals in order_lines]
        self.setup_line_ids = [(5, 0, 0)] + [(0, 0, vals) for vals in setup_lines]
        self.customer_line_ids = [(5, 0, 0)] + [(0, 0, vals) for vals in customer_lines]
        self._autofill_vendor()
        if warning:
            return {'warning': {'title': 'PR sudah dipakai', 'message': warning}}

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

    def button_approve(self, force=False):
        """Tanggal Purchase yang sudah diketik di Quotation dipertahankan (Odoo mengisinya dengan waktu sekarang)."""
        typed = {order.id: order.date_approve for order in self if order.date_approve}
        result = super().button_approve(force=force)
        for order in self.filtered(lambda o: o.id in typed and o.date_approve != typed[o.id]):
            order.date_approve = typed[order.id]
        # RFQ hasil gabungan dikonfirmasi: RFQ asalnya ditutup supaya tidak dipesan dua kali.
        for order in self:
            originals = order.merged_from_ids.filtered(lambda o: o.state in ('draft', 'sent'))
            if originals:
                originals.with_context(skip_merge_release=True).button_cancel()
        return result


class PurchaseOrderSetupLine(models.Model):
    _name = 'purchase.order.setup.line'
    _description = 'Purchase Order Setup Line'

    order_id = fields.Many2one(
        'purchase.order',
        ondelete='cascade'
    )

    request_id = fields.Many2one('purchase.request', string='No. PR')

    setup_item_id = fields.Many2one(
        'usulan.dana.setup',
        string='Setup Item',
        required=True
    )

    description = fields.Text(
        string="Description",
        store=True
    )

    item_qty = fields.Float(
        string='Qty',
        default=1.0
    )