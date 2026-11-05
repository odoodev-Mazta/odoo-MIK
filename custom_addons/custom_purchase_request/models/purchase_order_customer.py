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
