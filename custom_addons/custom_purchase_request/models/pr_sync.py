from odoo import api, fields, models

EDITABLE_PO_STATES = ('draft', 'sent')


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def _sync_usulan_dana_po_lines(self):
        """Keterangan PO di Usulan Dana (yang masih Draft) mengikuti isi PO terbaru."""
        for order in self:
            for usulan in order.usulan_dana_ids.filtered(lambda u: u.state == 'draft'):
                old = usulan.po_line_ids.filtered(lambda l: l.purchase_order_id == order)
                usulan.write({
                    'po_line_ids': [(2, line.id) for line in old]
                    + [(0, 0, vals) for vals in usulan._prepare_po_lines(order)],
                })


class PurchaseOrderLineSync(models.Model):
    _inherit = 'purchase.order.line'

    _SYNC_FIELDS = {'product_id', 'product_qty', 'price_unit', 'name', 'product_uom_id'}

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines.order_id._sync_usulan_dana_po_lines()
        return lines

    def write(self, vals):
        result = super().write(vals)
        if self._SYNC_FIELDS & vals.keys():
            self.order_id._sync_usulan_dana_po_lines()
        return result

    def unlink(self):
        orders = self.order_id
        result = super().unlink()
        orders.exists()._sync_usulan_dana_po_lines()
        return result


class PurchaseOrderCustomerLineSync(models.Model):
    _inherit = 'purchase.order.customer.line'

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines.order_id._sync_usulan_dana_po_lines()
        return lines

    def write(self, vals):
        result = super().write(vals)
        if vals.keys() & {'qty', 'request_qty', 'request_id', 'product_id', 'uom_id', 'mou_id',
                          'sale_order_id', 'description', 'customer_id', 'allocate_product_id'}:
            self.order_id._sync_usulan_dana_po_lines()
        return result

    def unlink(self):
        orders = self.order_id
        result = super().unlink()
        orders.exists()._sync_usulan_dana_po_lines()
        return result


class PurchaseRequestLineSync(models.Model):
    """Perubahan di PR diteruskan ke Keterangan PR di PO, lalu ke Keterangan PO di Usulan Dana."""
    _inherit = 'purchase.request.line'

    def _po_rows(self, description, include_remainder=False):
        """Baris Keterangan PR di PO yang berasal dari baris PR ini."""
        self.ensure_one()
        domain = [('request_id', '=', self.request_id.id), ('product_id', '=', self.product_id.id)]
        if not include_remainder:
            domain.append(('is_remainder', '=', False))
        rows = self.env['purchase.order.customer.line'].search(domain)
        return rows.filtered(lambda r: (r.description or False) == (description or False))

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if not self.env.context.get('skip_pr_sync'):
            lines._propagate_new_lines()
        return lines

    def write(self, vals):
        watched = {'description', 'product_qty'}
        if self.env.context.get('skip_pr_sync') or not watched & vals.keys():
            return super().write(vals)
        before = {line.id: (line.description, line.product_qty) for line in self}
        result = super().write(vals)
        for line in self:
            if line.product_id and not line.display_type and line.line_type == 'product':
                line._propagate_changes(*before[line.id])
        return result

    def _propagate_new_lines(self):
        """Baris baru di PR yang sudah dipakai PO (RFQ) ikut ditambahkan ke PO itu."""
        Customer = self.env['purchase.order.customer.line']
        for line in self:
            if not line.product_id or line.display_type or line.line_type != 'product' or not line.request_id:
                continue
            orders = Customer.search([('request_id', '=', line.request_id.id)]).order_id
            for order in orders:
                if order.state not in EDITABLE_PO_STATES or line._po_rows(line.description) & order.customer_line_ids:
                    continue
                uom = line.product_uom or line.product_id.uom_id
                existing = order.order_line.filtered(
                    lambda l: not l.display_type and l.product_id == line.product_id and l.product_uom_id == uom
                )[:1]
                if existing:
                    existing.product_qty += line.product_qty
                else:
                    order.write({'order_line': [(0, 0, {
                        'product_id': line.product_id.id,
                        'name': line.description or line.product_id.display_name,
                        'product_qty': line.product_qty,
                        'product_uom_id': uom.id,
                        'price_unit': line.price_unit,
                        'date_planned': line.date_planned or fields.Date.context_today(self),
                        'tax_ids': [(6, 0, line.tax_ids.ids)],
                    })]})
                order.write({'customer_line_ids': [(0, 0, {
                    'request_id': line.request_id.id,
                    'mou_id': line.request_id.mou_id.id,
                    'customer_id': line.request_id.mou_id.nama_cust.id or line.request_id.customer_id.id,
                    'sale_order_id': (line.sale_order_id or line.request_id.sale_order_id).id,
                    'product_id': line.product_id.id,
                    'description': line.description or False,
                    'qty': line.product_qty,
                    'request_qty': line.product_qty,
                    'uom_id': uom.id,
                })]})
                order.message_post(
                    body=f'Barang baru dari {line.request_id.name} ditambahkan: '
                         f'{line.product_id.display_name} ({line.product_qty:g}).'
                )

    def _propagate_changes(self, old_description, old_qty):
        self.ensure_one()
        rows = self._po_rows(old_description, include_remainder=True)
        if not rows:
            return
        orders = rows.order_id
        new_description = self.description or False

        if (old_description or False) != new_description:
            rows.with_context(skip_remainder_sync=True).write({'description': new_description})
            for order in orders:
                order_lines = order.order_line.filtered(
                    lambda l: not l.display_type and l.product_id == self.product_id
                    and l.name == (old_description or self.product_id.display_name)
                )
                order_lines.write({'name': new_description or self.product_id.display_name})

        if abs(old_qty - self.product_qty) > 1e-9:
            delta = self.product_qty - old_qty
            for order in orders:
                order_rows = rows.filtered(lambda r: r.order_id == order and not r.is_remainder)
                single = len(order_rows) == 1 and not rows.filtered(
                    lambda r: r.order_id == order and r.is_remainder)
                if order.state in EDITABLE_PO_STATES and single and abs(order_rows.qty - order_rows.request_qty) < 1e-9:
                    order_rows.with_context(skip_remainder_sync=True).write({
                        'qty': self.product_qty, 'request_qty': self.product_qty,
                    })
                    order_line = order.order_line.filtered(
                        lambda l: not l.display_type and l.product_id == self.product_id
                        and (not order_rows.uom_id or l.product_uom_id == order_rows.uom_id)
                    )[:1]
                    if order_line:
                        order_line.product_qty = max(order_line.product_qty + delta, 0.0)
                    order.message_post(
                        body=f'Qty {self.product_id.display_name} di {self.request_id.name} berubah '
                             f'{old_qty:g} → {self.product_qty:g}; PO ikut disesuaikan.'
                    )
                else:
                    order.message_post(
                        body=f'Qty {self.product_id.display_name} di {self.request_id.name} berubah '
                             f'{old_qty:g} → {self.product_qty:g}. Belum otomatis diterapkan '
                             '(PO sudah dikonfirmasi atau qty sudah dibagi ke beberapa customer); cek manual.'
                    )
        orders._sync_usulan_dana_po_lines()
