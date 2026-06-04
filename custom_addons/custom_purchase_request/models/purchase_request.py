from odoo import api, fields, models

class PurchaseRequest(models.Model):
    _name = 'purchase.request'
    _description = 'Purchase Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(
        string='PR Number',
        required=True,
        copy=False,
        readonly=True,
        default='New'
    )

    department_id = fields.Many2one(
        'hr.department',
        string='Department'
    )

    pic_dept = fields.Many2one('hr.employee',
        string='PIC Department'
    )

    whatsapp_no = fields.Char(
        string='No WhatsApp'
    )

    estimated_date = fields.Date(
        string='Estimated Arrival Date'
    )

    deliver_to = fields.Many2one('res.company',
        string='Deliver To'
    )

    vendor_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        domain=[('supplier_rank', '>', 0)]
    )

    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Attachments'
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('pr', 'Purchase Request'),
        ('po', 'Purchase Order'),
        ('ud', 'Usulan Dana'),
    ], default='draft', tracking=True)

    is_urgent = fields.Boolean(
        string='Urgent'
    )

    request_line_ids = fields.One2many(
        'purchase.request.line',
        'request_id',
        string='Products'
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )

    total_amount = fields.Monetary(
        string='Total Amount',
        compute='_compute_total_amount',
        store=True,
        currency_field='currency_id'
    )

    total_qty = fields.Float(
        string='Total Qty',
        compute='_compute_total_amount',
        store=True
    )

    date_usulan = fields.Date(
        string='Tgl Usulan',
        default=fields.Date.today,
    )

    product_summary = fields.Char(
        string='Item / Produk',
        compute='_compute_product_summary',
        store=True,
    )

    usulan_dana_id = fields.Many2one(
        'usulan.usulan.dana',
        string='No. Usulan Dana',
        tracking=True
    )

    product_line_ids = fields.One2many(
        'purchase.request.line',
        compute='_compute_line_split',
        inverse='_inverse_product_line_ids',
        string='Products',
        store=False,
    )

    item_line_ids = fields.One2many(
        'purchase.request.line',
        compute='_compute_line_split',
        inverse='_inverse_item_line_ids',
        string='Items',
        store=False,
    )

    def write(self, vals):
        res = super().write(vals)
        if vals.get('attachment_ids'):
            self.message_post(
                body="Attachment uploaded",
                attachment_ids=self.attachment_ids.ids
            )
        return res

    @api.depends('request_line_ids.product_id')
    def _compute_product_summary(self):
        for rec in self:
            products = rec.request_line_ids.mapped('product_id.name')
            if not products:
                rec.product_summary = ''
            elif len(products) == 1:
                rec.product_summary = products[0]
            else:
                rec.product_summary = f"{products[0]} (+{len(products) - 1} lainnya)"

    @api.depends('request_line_ids.price_subtotal',
                 'request_line_ids.product_qty')
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = sum(rec.request_line_ids.mapped('price_subtotal'))
            rec.total_qty = sum(rec.request_line_ids.mapped('product_qty'))

    def action_submit(self):
        for rec in self:
            rec.state = 'pr'

    def action_to_po(self):
        for rec in self:
            rec.state = 'po'

    def action_to_usulan_dana(self):
        for rec in self:
            rec.state = 'ud'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'purchase.request'
                ) or '/'
        return super().create(vals_list)

    @api.depends('request_line_ids', 'request_line_ids.line_type', 'request_line_ids.product_id','request_line_ids.setup_item_id')
    def _compute_line_split(self):
        for rec in self:
            rec.product_line_ids = rec.request_line_ids.filtered(
                lambda l: l.line_type == 'product'
            )

            rec.item_line_ids = rec.request_line_ids.filtered(
                lambda l: l.line_type == 'setup'
            )

    @api.depends('request_line_ids', 'request_line_ids.line_type', 'request_line_ids.product_id',
                 'request_line_ids.setup_item_id')
    def _compute_line_split(self):
        for rec in self:
            rec.product_line_ids = rec.request_line_ids.filtered(lambda l: l.line_type == 'product')
            rec.item_line_ids = rec.request_line_ids.filtered(lambda l: l.line_type == 'setup')

    def _inverse_product_line_ids(self):
        for rec in self:
            other_lines = rec.request_line_ids.filtered(lambda l: l.line_type != 'product')
            rec.request_line_ids = other_lines + rec.product_line_ids

    def _inverse_item_line_ids(self):
        for rec in self:
            other_lines = rec.request_line_ids.filtered(lambda l: l.line_type != 'setup')
            rec.request_line_ids = other_lines + rec.item_line_ids

    @api.onchange('usulan_dana_id')
    def _onchange_usulan_dana(self):
        if not self.usulan_dana_id:
            return

        self.currency_id = self.usulan_dana_id.currency_id.id

        self.request_line_ids = [(5, 0, 0)]

        lines = []

        for ud_line in self.usulan_dana_id.line_ids:

            vals = {
                'price_unit': ud_line.price_unit,
                'tax_ids': [(6, 0, ud_line.tax_ids.ids)],
            }

            if ud_line.product_id:
                vals.update({
                    'line_type': 'product',
                    'product_id': ud_line.product_id.id,
                    'product_qty': ud_line.quantity,
                    'currency_id': ud_line.currency_id.id,
                    'product_uom': ud_line.uom_id.id,
                    'name': ud_line.product_id.display_name,
                })

            elif ud_line.setup_item_id:
                vals.update({
                    'line_type': 'setup',
                    'setup_item_id': ud_line.setup_item_id.id,
                    'item_qty': ud_line.quantity,
                    'name': ud_line.setup_item_id.name,
                })

            lines.append((0, 0, vals))

        self.request_line_ids = lines

    def action_create_usulan_dana(self):
        self.ensure_one()

        lines = []

        for line in self.request_line_ids:
            if line.display_type:
                continue

            if line.product_id:
                lines.append((0, 0, {
                    'line_type': 'product',
                    'product_id': line.product_id.id,
                    'quantity': line.product_qty,
                    'price_unit': line.price_unit,
                }))
            if line.setup_item_id:
                lines.append((0, 0, {
                    'line_type': 'setup',
                    'setup_item_id': line.setup_item_id.id,
                    'quantity': line.item_qty,
                    'price_unit': 0.0,
                }))

        usulan = self.env['usulan.usulan.dana'].create({
            'department_id': self.department_id.id,
            'vendor_id': self.vendor_id.id,
            'currency_id': self.currency_id.id,
            'tgl_usulan': self.date_usulan,
            'description': f'Generate dari PR {self.name}',
            # 'purchase_request_name': self.name,
            'line_ids': lines
        })

        self.write({
            'state': 'ud',
            'usulan_dana_id': usulan.id,
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'usulan.usulan.dana',
            'res_id': usulan.id,
            'view_mode': 'form',
            'target': 'current',
        }

class PurchaseRequestLine(models.Model):
    _name = 'purchase.request.line'
    _description = 'Purchase Request Line'

    request_id = fields.Many2one('purchase.request', ondelete='cascade')
    sequence = fields.Integer(default=10)
    display_type = fields.Selection([
        ('line_section', 'Section'),
        ('line_note', 'Note'),
    ])
    product_id = fields.Many2one('product.product', string='Product', required=False)
    name = fields.Text(string='Description')
    product_qty = fields.Float(string='Quantity', default=1.0)
    item_qty = fields.Float(
        string='Item Qty',
        default=1.0
    )
    product_uom = fields.Many2one('uom.uom', string='Unit of Measure')
    price_unit = fields.Float(string='Unit Price')
    tax_ids = fields.Many2many('account.tax', string='Taxes')

    currency_id = fields.Many2one(
        'res.currency',
        store=True
    )

    price_subtotal = fields.Monetary(
        string='Amount',
        compute='_compute_amount',
        store=True,
        currency_field='currency_id'
    )

    date_planned = fields.Date(string='Scheduled Date')
    setup_item_id = fields.Many2one(
        'usulan.dana.setup',
        string="Setup Item",
        required=False
    )

    line_type = fields.Selection([
        ('product', 'Product'),
        ('setup', 'Setup Item'),
    ], required=True, default='product')

    @api.depends('product_qty', 'price_unit', 'currency_id')
    def _compute_amount(self):
        for line in self:
            currency = line.currency_id or line.request_id.currency_id

            if currency:
                line.price_subtotal = currency.round(
                    line.product_qty * line.price_unit
                )
            else:
                line.price_subtotal = (
                        line.product_qty * line.price_unit
                )