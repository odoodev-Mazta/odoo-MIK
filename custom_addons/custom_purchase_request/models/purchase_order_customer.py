from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import UserError


class PurchaseOrderCustomerLine(models.Model):
    _name = 'purchase.order.customer.line'
    _description = 'Rincian Customer PR pada PO'
    _order = 'order_id, sequence, id'

    order_id = fields.Many2one('purchase.order', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    request_id = fields.Many2one('purchase.request', string='No. PR')
    mou_id = fields.Many2one('draft.maklon', string='No. MOU', domain=[('state', '=', 'mou')])
    customer_id = fields.Many2one(
        'res.partner', string='Customer',
        compute='_compute_customer_id', store=True, readonly=False,
    )
    sale_order_id = fields.Many2one('sale.order', string='Sales Order', domain="[('mou_id', '=', mou_id)]")
    product_id = fields.Many2one('product.product', string='Produk', required=True)
    qty = fields.Float(string='Qty', default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit')
    po_qty = fields.Float(string='Total di PO', compute='_compute_po_qty')
    recommended_vendor_1 = fields.Char(related='request_id.recommended_vendor_1', string='Rekomendasi Vendor 1')
    recommended_vendor_2 = fields.Char(related='request_id.recommended_vendor_2', string='Rekomendasi Vendor 2')
    vendor_id = fields.Many2one(related='order_id.partner_id', string='Vendor PO')
    allocate_product_id = fields.Many2one(
        'product.product', string='Alokasi ke Produk',
        help='Produk milik customer (mis. Stiker Amerta 20gr). Stok produk di kolom Produk dipindahkan ke produk ini.',
    )
    allocated_qty = fields.Float(string='Sudah Dialokasikan', readonly=True, copy=False)

    @api.depends('mou_id')
    def _compute_customer_id(self):
        for line in self:
            line.customer_id = line.mou_id.nama_cust or line.customer_id

    @api.depends('order_id.order_line.product_qty', 'order_id.order_line.product_id', 'product_id')
    def _compute_po_qty(self):
        for line in self:
            line.po_qty = sum(
                order_line.product_qty
                for order_line in line.order_id.order_line
                if not order_line.display_type and order_line.product_id == line.product_id
            )

    def _allocatable_qty(self):
        """Barang PO yang sudah diterima dan belum dialokasikan ke baris mana pun (satuan baris)."""
        self.ensure_one()
        order = self.order_id
        received = sum(
            ol.qty_received for ol in order.order_line
            if not ol.display_type and ol.product_id == self.product_id
        )
        used = sum(
            l.allocated_qty for l in order.customer_line_ids
            if l.product_id == self.product_id and l.id != self.id
        )
        return received - used - self.allocated_qty

    def _allocate(self, todo):
        """Ubah `todo` unit barang PO yang sudah masuk gudang menjadi produk milik customer."""
        self.ensure_one()
        source, target, order = self.product_id, self.allocate_product_id, self.order_id
        qty_source = self.uom_id._compute_quantity(todo, source.uom_id) if self.uom_id else todo
        qty_target = self.uom_id._compute_quantity(todo, target.uom_id) if self.uom_id else todo
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', order.company_id.id)], limit=1)
        adjust_loc = self.env['stock.location'].sudo().search(
            [('usage', '=', 'inventory'), ('company_id', 'in', [order.company_id.id, False])], limit=1)
        if not warehouse or not adjust_loc:
            raise UserError('Gudang atau lokasi Inventory Adjustment tidak ditemukan.')
        stock_loc = warehouse.lot_stock_id
        origin = f'{order.name} - Alokasi {self.customer_id.name or ""} {self.request_id.name or ""}'.strip()
        moves = self.env['stock.move'].sudo().create([
            {
                'product_id': source.id, 'product_uom': source.uom_id.id, 'product_uom_qty': qty_source,
                'location_id': stock_loc.id, 'location_dest_id': adjust_loc.id,
                'company_id': order.company_id.id, 'origin': origin,
            },
            {
                'product_id': target.id, 'product_uom': target.uom_id.id, 'product_uom_qty': qty_target,
                'location_id': adjust_loc.id, 'location_dest_id': stock_loc.id,
                'company_id': order.company_id.id, 'origin': origin,
            },
        ])
        moves._action_confirm()
        for move, qty in zip(moves, (qty_source, qty_target)):
            move.quantity = qty
            move.picked = True
        moves._action_done()
        self.allocated_qty += todo
        order.message_post(body=(
            f'Stok dialokasikan: {todo:g} {source.display_name} menjadi {target.display_name} '
            f'untuk {self.customer_id.name or "-"} ({self.request_id.name or "-"}).'
        ))

    def _can_allocate(self):
        self.ensure_one()
        source, target = self.product_id, self.allocate_product_id
        return (
            target and target != source and source.is_storable and target.is_storable
            and source.tracking == 'none' and target.tracking == 'none'
        )

    def action_allocate(self):
        """Tombol manual: alokasikan barang PO yang sudah diterima."""
        for line in self:
            if not line.allocate_product_id:
                raise UserError('Isi kolom "Alokasi ke Produk" lebih dulu.')
            if not line._can_allocate():
                raise UserError(
                    'Produk harus berbeda, kedua produk dicentang Track Inventory, dan tanpa Lot/Serial.'
                )
            todo = min(line.qty - line.allocated_qty, line._allocatable_qty())
            if todo <= 0:
                raise UserError(
                    'Belum ada barang dari PO ini yang diterima (atau sudah teralokasi semua). '
                    'Alokasi berjalan otomatis saat Receipt PO di-validate.'
                )
            line._allocate(todo)
        return True

    def _auto_allocate(self):
        """Dipanggil saat Receipt PO selesai: barang yang masuk langsung jadi produk customer."""
        for line in self:
            if not line._can_allocate():
                continue
            todo = min(line.qty - line.allocated_qty, line._allocatable_qty())
            if todo > 0:
                line._allocate(todo)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id and not self.uom_id:
            self.uom_id = self.product_id.uom_id


class PurchaseOrderAddRequestWizard(models.TransientModel):
    _name = 'purchase.order.add.request.wizard'
    _description = 'Ambil Barang dari PR'

    order_id = fields.Many2one('purchase.order', required=True, ondelete='cascade')
    request_ids = fields.Many2many(
        'purchase.request',
        string='Purchase Request',
        domain="[('state', '!=', 'cancelled'), ('company_id', '=', company_id)]",
    )
    company_id = fields.Many2one(related='order_id.company_id')
    warning = fields.Text(compute='_compute_warning')

    @api.depends('request_ids', 'order_id')
    def _compute_warning(self):
        for wizard in self:
            wizard.warning = wizard.order_id._warning_requests_in_use(wizard.request_ids)

    def action_add(self):
        self.ensure_one()
        if not self.request_ids:
            raise UserError('Pilih minimal satu PR.')
        self.order_id._add_requests(self.request_ids)
        return {'type': 'ir.actions.act_window_close'}


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _action_done(self):
        result = super()._action_done()
        orders = self.filtered(lambda p: p.state == 'done').move_ids.purchase_line_id.order_id
        orders.customer_line_ids.filtered('allocate_product_id')._auto_allocate()
        return result
