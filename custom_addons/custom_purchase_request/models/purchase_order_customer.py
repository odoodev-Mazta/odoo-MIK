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
    description = fields.Char(string='Deskripsi', help='Deskripsi barang yang ditulis di PR (mis. ukuran/gramasi).')
    qty = fields.Float(string='Qty', default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit')
    po_qty = fields.Float(string='Total di PO', compute='_compute_po_qty')
    recommended_vendor_1 = fields.Char(related='request_id.recommended_vendor_1', string='Rekomendasi Vendor 1')
    recommended_vendor_2 = fields.Char(related='request_id.recommended_vendor_2', string='Rekomendasi Vendor 2')
    recommended_partner_ids = fields.Many2many(
        'res.partner', string='Vendor di PR', compute='_compute_recommended_partner_ids',
    )
    vendor_choice_id = fields.Many2one(
        'res.partner', string='Vendor',
        compute='_compute_vendor_choice_id', store=True, readonly=False,
        domain="[('id', 'in', recommended_partner_ids)]",
        help='Pilih salah satu vendor yang direkomendasikan di PR. Vendor PO mengikuti pilihan ini.',
    )
    vendor_id = fields.Many2one(related='order_id.partner_id', string='Vendor PO')
    allocate_product_id = fields.Many2one(
        'product.product', string='Alokasi ke Produk',
        help='Produk milik customer (mis. Stiker Amerta 20gr). Stok produk di kolom Produk dipindahkan ke produk ini.',
    )
    allocated_qty = fields.Float(string='Sudah Dialokasikan', readonly=True, copy=False)
    request_qty = fields.Float(
        string='Qty di PR',
        help='Qty asli barang ini di PR. Bila Qty diturunkan di bawah angka ini, sisanya otomatis '
             'dibuatkan baris baru.',
    )
    is_remainder = fields.Boolean(
        string='Sisa',
        readonly=True,
        help='Baris otomatis berisi sisa qty PR yang tidak diambil di PO ini. '
             'Tidak ikut dihitung sebagai alokasi dan tidak mengubah qty barang PO.',
    )

    # ------------------------------------------------------------------
    # Sisa qty PR: Qty diturunkan (mis. 216 -> 82) => baris sisa (134) dibuat otomatis
    # ------------------------------------------------------------------
    def _remainder_key(self):
        """Baris 'sama' = PR, produk, unit, MOU, SO, dan deskripsi yang sama dalam satu PO."""
        self.ensure_one()
        return (
            self.order_id.id, self.request_id.id, self.product_id.id, self.uom_id.id,
            self.mou_id.id, self.sale_order_id.id, self.description or False,
        )

    def _shortfall(self):
        """Qty PR yang belum diambil oleh baris ini."""
        self.ensure_one()
        if self.is_remainder or not self.request_id or self.request_qty <= 0:
            return 0.0
        return max(self.request_qty - self.qty, 0.0)

    @api.model
    def _sync_remainders(self, keys):
        """Samakan baris sisa dengan selisih qty PR untuk tiap kelompok baris."""
        for key in keys:
            if not key[0]:
                continue
            group = self.search([('order_id', '=', key[0])]).filtered(lambda l: l._remainder_key() == key)
            mains = group.filtered(lambda l: not l.is_remainder)
            remainders = group - mains
            short = sum(line._shortfall() for line in mains)
            if short <= 1e-6:
                remainders.unlink()
                continue
            if remainders:
                remainders[0].with_context(skip_remainder_sync=True).write({'qty': short})
                (remainders - remainders[0]).unlink()
                continue
            main = mains.filtered(lambda l: l._shortfall() > 0)[:1]
            self.with_context(skip_remainder_sync=True).create({
                'order_id': main.order_id.id,
                'sequence': main.sequence,
                'request_id': main.request_id.id,
                'mou_id': main.mou_id.id,
                'customer_id': main.customer_id.id,
                'sale_order_id': main.sale_order_id.id,
                'product_id': main.product_id.id,
                'description': main.description,
                'uom_id': main.uom_id.id,
                'qty': short,
                'request_qty': 0.0,
                'is_remainder': True,
            })

    def _adjust_order_qty(self, delta):
        """Qty barang di tab Item Barang ikut berubah sebesar `delta`.

        Saat turun, qty tidak pernah lebih rendah dari total qty yang diambil di Keterangan PR,
        jadi tidak terpotong dua kali bila Item Barang sudah diturunkan manual.
        """
        self.ensure_one()
        order_line = self.order_id.order_line.filtered(
            lambda l: not l.display_type and l.product_id == self.product_id
            and (not self.uom_id or l.product_uom_id == self.uom_id)
        )[:1]
        if not order_line or not delta:
            return
        new_qty = order_line.product_qty + delta
        if delta < 0:
            taken = sum(
                l.qty for l in self.search([('order_id', '=', self.order_id.id)])
                if not l.is_remainder and l.product_id == self.product_id and l.uom_id == self.uom_id
            )
            new_qty = max(new_qty, min(taken, order_line.product_qty))
        order_line.product_qty = max(new_qty, 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('is_remainder') and not vals.get('request_qty'):
                vals['request_qty'] = vals.get('qty', 1.0)
        lines = super().create(vals_list)
        if not self.env.context.get('skip_remainder_sync'):
            self._sync_remainders({line._remainder_key() for line in lines})
        return lines

    def write(self, vals):
        watched = {'qty', 'request_qty', 'request_id', 'product_id', 'uom_id', 'mou_id',
                   'sale_order_id', 'description'}
        if self.env.context.get('skip_remainder_sync') or not watched & vals.keys():
            return super().write(vals)
        before = {line.id: (line._remainder_key(), line._shortfall()) for line in self}
        result = super().write(vals)
        keys = set()
        for line in self:
            old_key, old_short = before[line.id]
            new_key = line._remainder_key()
            keys.update((old_key, new_key))
            if old_key == new_key and not line.is_remainder:
                line._adjust_order_qty(old_short - line._shortfall())
        self._sync_remainders(keys)
        return result

    def unlink(self):
        keys = set()
        if not self.env.context.get('skip_remainder_sync'):
            keys = {line._remainder_key() for line in self if not line.is_remainder}
        result = super().unlink()
        self._sync_remainders(keys)
        return result

    @api.depends('request_id.recommended_vendor_1', 'request_id.recommended_vendor_2', 'order_id.company_id')
    def _compute_recommended_partner_ids(self):
        for line in self:
            partners = self.env['res.partner']
            names = {
                name.strip()
                for name in (line.request_id.recommended_vendor_1, line.request_id.recommended_vendor_2)
                if name and name.strip()
            }
            for name in sorted(names):
                partners |= self.env['res.partner'].search([
                    ('name', '=ilike', name),
                    ('company_id', 'in', [False, line.order_id.company_id.id]),
                ])
            line.recommended_partner_ids = partners

    @api.depends('request_id')
    def _compute_vendor_choice_id(self):
        """Terisi otomatis bila PR hanya punya satu vendor terdaftar; selain itu kosong untuk dipilih."""
        for line in self:
            partners = line.recommended_partner_ids
            if line.vendor_choice_id in partners:
                continue
            line.vendor_choice_id = partners if len(partners) == 1 else False

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

    can_allocate_now = fields.Boolean(compute='_compute_allocation_state')
    allocation_state = fields.Char(string='Status Alokasi', compute='_compute_allocation_state')

    @api.depends('allocate_product_id', 'allocated_qty', 'qty', 'product_id',
                 'order_id.order_line.qty_received')
    def _compute_allocation_state(self):
        for line in self:
            target = line.allocate_product_id
            line.can_allocate_now = False
            if not target:
                line.allocation_state = False
            elif target == line.product_id:
                line.allocation_state = 'Masuk stok produk ini'
            elif line.allocated_qty >= line.qty > 0:
                line.allocation_state = 'Selesai'
            elif not line.id:
                line.allocation_state = 'Simpan dulu'
            elif line._allocatable_qty() > 0 and line._can_allocate():
                line.can_allocate_now = True
                line.allocation_state = 'Siap dialokasikan'
            else:
                line.allocation_state = 'Menunggu barang diterima'

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
        domain="[('state', '=', 'pr'), ('company_id', '=', company_id)]",
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


class UsulanUsulanDana(models.Model):
    _inherit = 'usulan.usulan.dana'

    po_customer_line_ids = fields.One2many(
        related='purchase_order_id.customer_line_ids',
        string='Keterangan PO',
        readonly=True,
    )
