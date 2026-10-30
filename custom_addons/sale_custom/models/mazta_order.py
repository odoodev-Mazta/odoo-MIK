from odoo import models, fields, api

class MaztaOrder(models.Model):
    _name = 'mazta.order'
    _description = 'Mazta Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Order Number', required=True, copy=False, readonly=True, default=lambda self: 'New')
    partner_id = fields.Many2one('res.partner', string='Customer', required=True, tracking=True)
    date_order = fields.Datetime(string='Order Date', default=fields.Datetime.now, tracking=True)
    user_id = fields.Many2one('res.users', string='Salesperson', default=lambda self: self.env.user, tracking=True)
    
    # Relasi ke Order Lines (Tab Produk)
    order_line = fields.One2many('mazta.order.line', 'order_id', string='Order Lines', copy=True)
    
    amount_total = fields.Monetary(string='Total', compute='_compute_amount', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    state = fields.Selection([
        ('draft', 'Quotation'),
        ('sale', 'Sales Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, copy=False)


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('mazta.order') or 'New'
        return super().create(vals_list)

    @api.depends('order_line.price_subtotal')
    def _compute_amount(self):
        for order in self:
            order.amount_total = sum(line.price_subtotal for line in order.order_line)
            
    def action_confirm(self):
        for order in self:
            order.state = 'sale'
    
    def action_cancel(self):
        for order in self:
            if order.state == 'sale':
                pass
            order.write({'state': 'cancel'})
        return True
    
    def action_draft(self):
        for order in self:
            order.write({'state': 'draft'})
        return True
    
    def action_print(self):
        """Memanggil action report PDF yang terdaftar"""
        self.ensure_one()
        return self.env.ref('sale_custom.action_report_mazta_order').report_action(self)

    def action_preview_order(self):
        """Mengarahkan preview ala portal web customer"""
        self.ensure_one()
        # Jika Anda ingin mengarah ke halaman website/portal kustom, arahkan URL-nya ke route Anda.
        # Sementara itu kita arahkan ke form dengan mode preview atau URL web.
        return {
            'type': 'ir.actions.act_url',
            'url': f'/my/mazta/orders/{self.id}', # Sesuaikan jika nanti sudah buat controller webnya
            'target': 'self',
        }

class MaztaOrderLine(models.Model):
    _name = 'mazta.order.line'
    _description = 'Mazta Order Line'

    order_id = fields.Many2one('mazta.order', string='Order Reference', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    name = fields.Text(string='Description', required=True)
    product_uom_qty = fields.Float(string='Quantity', digits='Product Unit of Measure', default=1.0)
    price_unit = fields.Float(string='Unit Price', digits='Product Price', default=0.0)
    tax_id = fields.Many2many('account.tax', string='Taxes')
    price_subtotal = fields.Monetary(string='Subtotal', compute='_compute_subtotal', store=True)
    currency_id = fields.Many2one('res.currency', related='order_id.currency_id', store=True, readonly=True)

    @api.depends('product_uom_qty', 'price_unit', 'tax_id')
    def _compute_subtotal(self):
        for line in self:
            subtotal = line.product_uom_qty * line.price_unit
            # Jika ingin kalkulasi pajak sederhana, bisa disesuaikan di sini
            line.price_subtotal = subtotal

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.get_product_multiline_description_sale()
            self.price_unit = self.product_id.lst_price