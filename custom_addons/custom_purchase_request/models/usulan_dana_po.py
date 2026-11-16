from odoo import api, fields, models
from odoo.exceptions import UserError


class UsulanDanaPoLine(models.Model):
    """Keterangan PO pada Usulan Dana: rincian barang per No. PO (padanan Keterangan PR di PO)."""
    _name = 'usulan.dana.po.line'
    _description = 'Keterangan PO pada Usulan Dana'
    _order = 'usulan_id, sequence, id'

    usulan_id = fields.Many2one('usulan.usulan.dana', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    purchase_order_id = fields.Many2one('purchase.order', string='No. PO', required=True)
    vendor_id = fields.Many2one(related='purchase_order_id.partner_id', string='Vendor')
    request_id = fields.Many2one('purchase.request', string='No. PR')
    mou_id = fields.Many2one('draft.maklon', string='No. MOU')
    customer_id = fields.Many2one('res.partner', string='Customer')
    sale_order_id = fields.Many2one('sale.order', string='No. SO')
    product_id = fields.Many2one('product.product', string='Produk')
    description = fields.Char(string='Deskripsi')
    qty = fields.Float(string='Qty')
    uom_id = fields.Many2one('uom.uom', string='Unit')
    price_unit = fields.Float(string='Price')
    currency_id = fields.Many2one('res.currency', string='Currency')
    price_subtotal = fields.Monetary(string='Subtotal', compute='_compute_price_subtotal', currency_field='currency_id')
    allocate_product_id = fields.Many2one('product.product', string='Alokasi ke Produk')
    is_remainder = fields.Boolean(string='Sisa', help='Bagian barang PO yang belum dialokasikan ke customer.')

    @api.depends('qty', 'price_unit')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.qty * line.price_unit


class UsulanUsulanDana(models.Model):
    _inherit = 'usulan.usulan.dana'

    po_line_ids = fields.One2many('usulan.dana.po.line', 'usulan_id', string='Keterangan PO')

    def _prepare_po_lines(self, order):
        """Baris Keterangan PO dari satu PO: dibagi per customer bila PO punya Keterangan PR."""
        customer_lines = order.customer_line_ids.filtered(lambda l: not l.is_remainder)
        rows = []
        for line in order.order_line.filtered(lambda l: not l.display_type):
            base = {
                'purchase_order_id': order.id,
                'product_id': line.product_id.id,
                'uom_id': line.product_uom_id.id,
                'price_unit': line.price_unit,
                'currency_id': order.currency_id.id,
            }
            matching = customer_lines.filtered(
                lambda l: l.product_id == line.product_id and (not l.uom_id or l.uom_id == line.product_uom_id)
            )
            if not matching:
                rows.append({
                    **base,
                    'mou_id': order.mou_id.id,
                    'customer_id': order.customer_id.id,
                    'sale_order_id': order.sale_order_id.id,
                    'description': line.name,
                    'qty': line.product_qty,
                })
                continue
            for cl in matching:
                rows.append({
                    **base,
                    'request_id': cl.request_id.id,
                    'mou_id': cl.mou_id.id,
                    'customer_id': cl.customer_id.id,
                    'sale_order_id': cl.sale_order_id.id,
                    'description': cl.description or line.name,
                    'qty': cl.qty,
                    'allocate_product_id': cl.allocate_product_id.id,
                })
            left = line.product_qty - sum(matching.mapped('qty'))
            if left > 1e-6:
                rows.append({
                    **base,
                    'description': f'Belum dialokasikan ke customer ({line.name})',
                    'qty': left,
                    'is_remainder': True,
                })
        return rows

    @api.onchange('purchase_order_ids')
    def _onchange_purchase_order_ids(self):
        result = super()._onchange_purchase_order_ids()
        rows = []
        for order in self.purchase_order_ids:
            rows += [(0, 0, vals) for vals in self._prepare_po_lines(order)]
        self.po_line_ids = [(5, 0, 0)] + rows
        return result

    def _add_orders(self, orders):
        """Tambahkan PO ke Usulan Dana ini tanpa menghapus baris yang sudah ada."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError('PO hanya bisa ditambahkan saat Usulan Dana masih Draft.')
        orders -= self.purchase_order_ids
        if not orders:
            raise UserError('PO yang dipilih sudah ada di Usulan Dana ini.')
        item_cmds, po_cmds = [], []
        for order in orders:
            item_cmds += [(0, 0, vals) for vals in self._prepare_item_lines(order)]
            po_cmds += [(0, 0, vals) for vals in self._prepare_po_lines(order)]
        all_orders = self.purchase_order_ids | orders
        values = {
            'purchase_order_ids': [(4, order.id) for order in orders],
            'line_ids': item_cmds,
            'po_line_ids': po_cmds,
            'description': f"Tagihan atas PO: {', '.join(all_orders.mapped('name'))}",
        }
        if not self.vendor_id:
            values['vendor_id'] = orders[0].partner_id.id
        self.write(values)
        if len(all_orders.partner_id) > 1 or len(all_orders.currency_id) > 1:
            self.message_post(body='Perhatian: PO yang dipilih punya vendor atau mata uang berbeda.')

    def action_add_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Ambil dari PO',
            'res_model': 'usulan.dana.add.po.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_usulan_id': self.id},
        }


class UsulanDanaAddPoWizard(models.TransientModel):
    _name = 'usulan.dana.add.po.wizard'
    _description = 'Ambil dari PO'

    usulan_id = fields.Many2one('usulan.usulan.dana', required=True, ondelete='cascade')
    order_ids = fields.Many2many(
        'purchase.order',
        string='Purchase Order',
        domain="[('state', 'in', ['purchase', 'done'])]",
    )
    warning = fields.Text(compute='_compute_warning')

    @api.depends('order_ids', 'usulan_id')
    def _compute_warning(self):
        for wizard in self:
            lines = []
            for order in wizard.order_ids:
                others = order.usulan_dana_ids.filtered(
                    lambda ud: ud.id != wizard.usulan_id.id and ud.state not in ('reject', 'cancel')
                )
                if others:
                    lines.append(f'{order.name} sudah ada di {", ".join(others.mapped("name"))}')
            wizard.warning = ('\n'.join(lines) + '\nPastikan tidak ditagihkan dua kali.') if lines else False

    def action_add(self):
        self.ensure_one()
        if not self.order_ids:
            raise UserError('Pilih minimal satu PO.')
        self.usulan_id._add_orders(self.order_ids)
        return {'type': 'ir.actions.act_window_close'}
