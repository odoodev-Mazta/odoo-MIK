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
        domain="[('state', '=', 'pr'), ('has_active_po', '=', False), ('company_id', '=', company_id)]"
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
    )

    @api.depends('purchase_request_id', 'customer_line_ids.request_id')
    def _compute_purchase_request_ids(self):
        for order in self:
            order.purchase_request_ids = order.purchase_request_id | order.customer_line_ids.request_id

    customer_line_warning = fields.Text(compute='_compute_customer_line_warning')

    @api.depends('customer_line_ids.qty', 'customer_line_ids.product_id',
                 'order_line.product_qty', 'order_line.product_id')
    def _compute_customer_line_warning(self):
        for order in self:
            if not order.customer_line_ids:
                order.customer_line_warning = False
                continue
            ordered = defaultdict(float)
            allocated = defaultdict(float)
            for line in order.order_line:
                if not line.display_type and line.product_id:
                    ordered[line.product_id] += line.product_qty
            for line in order.customer_line_ids:
                allocated[line.product_id] += line.qty
            messages = [
                f"{product.display_name}: qty PO {ordered[product]:g}, terbagi ke customer {allocated[product]:g}"
                for product in (ordered.keys() | allocated.keys())
                if abs(ordered[product] - allocated[product]) > 1e-6
            ]
            order.customer_line_warning = "\n".join(messages) or False

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
        'company_id',
    )
    def _compute_recommended_vendors(self):
        for order in self:
            request = order.purchase_request_id
            vendors = self.env['res.partner']
            unregistered = []
            names = {
                name.strip()
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

    def _sync_header_from_customer_lines(self):
        """Bagian atas PO: satu MOU/customer bila semua baris sama; kosong bila beragam."""
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
        """Merge bawaan Odoo menjumlahkan produk sama dan membatalkan RFQ lain: rincian customer ikut dipindah."""
        rfqs = self.filtered(lambda r: r.state in ('draft', 'sent'))
        grouped = defaultdict(lambda: self.browse())
        for rfq in rfqs:
            grouped[self._prepare_grouped_data(rfq)] += rfq
        plan = []
        for group in grouped.values():
            if len(group) > 1:
                oldest = min(group, key=lambda r: r.date_order)
                plan.append((oldest, group - oldest))
        for oldest, others in plan:
            (oldest | others)._ensure_customer_lines()
        result = super().action_merge()
        for oldest, others in plan:
            others.customer_line_ids.write({'order_id': oldest.id})
            others.setup_line_ids.write({'order_id': oldest.id})
            oldest._sync_header_from_customer_lines()
        return result

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
            order.customer_line_ids = [(0, 0, {
                'request_id': order.purchase_request_id.id,
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

        order_lines, setup_lines, customer_lines = self._prepare_request_lines(request)
        self.order_line = [(5, 0, 0)] + [(0, 0, vals) for vals in order_lines]
        self.setup_line_ids = [(5, 0, 0)] + [(0, 0, vals) for vals in setup_lines]
        self.customer_line_ids = [(5, 0, 0)] + [(0, 0, vals) for vals in customer_lines]

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
        return result


class PurchaseOrderSetupLine(models.Model):
    _name = 'purchase.order.setup.line'
    _description = 'Purchase Order Setup Line'

    order_id = fields.Many2one(
        'purchase.order',
        ondelete='cascade'
    )

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