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

    pic_dept = fields.Char(
        string='PIC Department'
    )

    whatsapp_no = fields.Char(
        string='No WhatsApp'
    )

    estimated_date = fields.Date(
        string='Estimated Arrival Date'
    )

    deliver_to = fields.Char(
        string='Deliver To'
    )

    vendor_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        domain=[('supplier_rank', '>', 0)]
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('pr', 'Purchase Request'),
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
            'tgl_usulan': self.date_usulan,
            'description': f'Generate dari PR {self.name}',
            'line_ids': lines
        })

        self.state = 'ud'

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'usulan.usulan.dana',
            'res_id': usulan.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # def action_create_usulan_dana(self):
    #     self.ensure_one()
    #     UsulanDana = self.env['usulan.usulan.dana']
    #
    #     usulan = UsulanDana.create({
    #         'name': 'New',
    #         'department_id': self.department_id.id,
    #         'vendor_id': self.vendor_id.id,
    #         'tgl_usulan': fields.Date.today(),
    #         'description': f"Generated from PR {self.name}",
    #         'purchase_request_id': self.id,
    #     })
    #
    #     UsulanLine = self.env['usulan.usulan.dana.line']
    #
    #     for line in self.request_line_ids:
    #         UsulanLine.create({
    #             'usulan_id': usulan.id,
    #             'setup_item_id': line.setup_item_id.id,
    #             'quantity': line.product_qty,
    #             'price_unit': line.price_unit,
    #             'tax_ids': [(6, 0, line.tax_ids.ids)],
    #             'purchase_request_line_id': line.id,
    #         })
    #
    #     self.state = 'ud'
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'res_model': 'usulan.usulan.dana',
    #         'res_id': usulan.id,
    #         'view_mode': 'form',
    #         'target': 'current',
    #     }

class PurchaseRequestLine(models.Model):
    _name = 'purchase.request.line'
    _description = 'Purchase Request Line'

    request_id = fields.Many2one('purchase.request', ondelete='cascade')
    sequence = fields.Integer(default=10)
    display_type = fields.Selection([
        ('line_section', 'Section'),
        ('line_note', 'Note'),
    ])
    product_id = fields.Many2one('product.product', string='Product')
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
        related='request_id.currency_id',
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

    @api.depends('product_qty', 'price_unit', 'currency_id')
    def _compute_amount(self):
        for line in self:
            line.price_subtotal = line.currency_id.round(
                line.product_qty * line.price_unit
            )