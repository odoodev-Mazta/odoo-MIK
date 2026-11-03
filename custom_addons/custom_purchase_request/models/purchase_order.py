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

        default_date = request.estimated_date or fields.Date.context_today(self)
        order_lines = [(5, 0, 0)]
        setup_lines = [(5, 0, 0)]
        for line in request.request_line_ids.filtered(lambda l: not l.display_type):
            if line.line_type == 'setup' and line.setup_item_id:
                setup_lines.append((0, 0, {
                    'setup_item_id': line.setup_item_id.id,
                    'description': line.description,
                    'item_qty': line.item_qty,
                }))
            elif line.product_id:
                order_lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'name': line.description or line.product_id.display_name,
                    'product_qty': line.product_qty,
                    'product_uom_id': (line.product_uom or line.product_id.uom_id).id,
                    'price_unit': line.price_unit,
                    'date_planned': line.date_planned or default_date,
                    'tax_ids': [(6, 0, line.tax_ids.ids)],
                }))
        if request.is_bulk_purchase:
            for line in request.bulk_line_ids:
                order_lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'name': line.product_id.display_name,
                    'product_qty': line.qty,
                    'product_uom_id': line.uom_id.id,
                    'price_unit': line.price_unit,
                    'date_planned': default_date,
                }))
        self.order_line = order_lines
        self.setup_line_ids = setup_lines

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