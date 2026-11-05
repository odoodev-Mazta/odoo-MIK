from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError

class PurchaseRequest(models.Model):
    _name = 'purchase.request'
    _description = 'Purchase Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    # Terbaru di atas: kotak pilihan PR (hanya 8 baris) dan daftar PR menampilkan PR terbaru lebih dulu.
    _order = 'id desc'
    # Cari PR lewat nomor, nama customer, atau nomor MOU (nomor PR sekarang bebas diketik).
    _rec_names_search = ['name', 'customer_id.name', 'mou_id.draft_name']

    name = fields.Char(
        string='PR Number',
        required=True,
        copy=False,
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

    # rekomen vendor 1
    recommended_vendor_1 = fields.Char(
        string='Vendor'
    )

    recommended_vendor_1_address = fields.Char(
        string='Alamat',
        readonly=False,
    )

    recommended_vendor_1_phone = fields.Char(
        string='No WA',
        readonly=False,
    )

    recommended_vendor_1_email = fields.Char(
        string='Email',
        readonly=False,
    )

    recommended_vendor_1_website = fields.Char(
        string='Website',
        readonly=False,
    )

    recommended_vendor_1_type = fields.Selection([
        ('online', 'Online'),
        ('offline', 'Offline'),
    ], string='Jenis')

    # rekomendasi vendor 2
    recommended_vendor_2 = fields.Char(
        string='Vendor 2'
    )

    recommended_vendor_2_address = fields.Char(
        string='Alamat Vendor 2',
        readonly=False,
    )

    recommended_vendor_2_phone = fields.Char(
        string='No WA Vendor 2',
        readonly=False,
    )

    recommended_vendor_2_email = fields.Char(
        string='Email Vendor 2',
        readonly=False,
    )

    recommended_vendor_2_website = fields.Char(
        string='Website Vendor 2',
        readonly=False,
    )

    recommended_vendor_2_type = fields.Selection([
        ('online', 'Online'),
        ('offline', 'Offline'),
    ], string='Jenis Vendor 2')

    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Attachments'
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('to_approve', 'Menunggu Approval'),
        ('pr', 'Purchase Request'),
        ('cancelled', 'Cancelled'),
    ], default='draft', tracking=True)

    purchase_purpose = fields.Selection(
        [('produksi', 'Produksi'), ('non_produksi', 'Non Produksi')],
        string='Kebutuhan', required=True, default='produksi', tracking=True,
        help='Produksi: bahan untuk produksi customer. Non Produksi: kebutuhan umum atau tambah stok.',
    )

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
        string='Produk',
        store=False,
    )

    item_line_ids = fields.One2many(
        'purchase.request.line',
        compute='_compute_line_split',
        inverse='_inverse_item_line_ids',
        string='Items',
        store=False,
    )

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

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    purchase_order_ids = fields.One2many(
        'purchase.order',
        'purchase_request_id',
        string='Purchase Order',
    )

    customer_line_ids = fields.One2many('purchase.order.customer.line', 'request_id', string='Rincian di PO')

    has_active_po = fields.Boolean(
        string='Sudah Ada PO',
        compute='_compute_has_active_po',
        store=True,
    )

    is_bulk_purchase = fields.Boolean(
        string="Pembelian Bulk"
    )

    bulk_line_ids = fields.One2many(
        'purchase.request.bulk.mou.line',
        'purchase_request_id',
        string='Bulk Allocation'
    )

    # purchase_order_id = fields.Many2one(
    #     'purchase.order',
    #     string='Purchase Order',
    #     readonly=True,
    #     copy=False,
    # )
    #
    # def action_create_po(self):
    #     self.ensure_one()
    #
    #     order_lines = []
    #
    #     for line in self.product_line_ids:
    #         order_lines.append((0, 0, {
    #             'product_id': line.product_id.id,
    #             'name': line.description or line.product_id.display_name,
    #             'product_qty': line.product_qty,
    #             'price_unit': line.price_unit,
    #             'date_planned': self.estimated_date,  # <-- ambil dari header PR
    #         }))
    #
    #     po = self.env['purchase.order'].create({
    #         'customer_id': self.customer_id.id,
    #         'mou_id': self.mou_id.id,
    #         'currency_id': self.currency_id.id,
    #         'order_line': order_lines,
    #     })
    #
    #     # Kosongkan tax
    #     po.order_line.write({
    #         'tax_ids': [(5, 0, 0)],
    #     })
    #
    #     self.purchase_order_id = po.id
    #
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'res_model': 'purchase.order',
    #         'res_id': po.id,
    #         'view_mode': 'form',
    #         'target': 'current',
    #     }

    def _active_orders(self):
        """RFQ/PO aktif yang memuat PR ini, baik lewat kolom No. PR maupun tab Customer PR."""
        self.ensure_one()
        if not self._origin.id:
            return self.env['purchase.order']
        orders = self._origin.purchase_order_ids
        lines = self.env['purchase.order.customer.line'].search([('request_id', '=', self._origin.id)])
        return (orders | lines.order_id).filtered(lambda po: po.state != 'cancel')

    @api.depends('purchase_order_ids', 'purchase_order_ids.state', 'customer_line_ids.order_id.state')
    def _compute_has_active_po(self):
        for rec in self:
            rec.has_active_po = bool(rec._active_orders())

    def action_create_po(self):
        """Buka form RFQ/PO baru; vendor dan baris terisi dari PR ini (onchange di PO)."""
        self.ensure_one()
        if self.state != 'pr':
            raise UserError('PO hanya bisa dibuat dari PR yang berstatus Purchase Request.')
        active = self._active_orders()
        if active:
            raise UserError(f'PR {self.name} sudah punya RFQ/PO aktif: {", ".join(active.mapped("name"))}.')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Request for Quotation',
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'target': 'current',
            'context': {'default_purchase_request_id': self.id, 'default_company_id': self.company_id.id},
        }

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

    def write(self, vals):
        res = super().write(vals)
        if vals.get('attachment_ids'):
            self.message_post(
                body="Attachment uploaded",
                attachment_ids=self.attachment_ids.ids
            )
        return res

    @api.onchange('customer_id')
    def _onchange_customer(self):
        if self.mou_id.nama_cust != self.customer_id:
            self.mou_id = False

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

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        """Produk diisi dari baris Sales Order; qty tetap bisa diubah."""
        if not self.sale_order_id or self.state != 'draft':
            return
        lines = self.sale_order_id.order_line.filtered(
            lambda line: not line.display_type and line.product_id and line.product_id.type != 'service'
        )
        self.product_line_ids = [Command.clear()] + [
            Command.create({
                'line_type': 'product',
                'product_id': line.product_id.id,
                'description': line.product_id.display_name,
                'product_qty': line.product_uom_qty,
                'product_uom': line.product_uom_id.id,
                'currency_id': self.currency_id.id,
            })
            for line in lines
        ]

    @api.onchange('mou_id')
    def _onchange_mou(self):
        if self.sale_order_id.mou_id != self.mou_id:
            self.sale_order_id = False
        if not self.mou_id:
            return
        self._fill_single_sale_order()
        # set customer otomatis
        self.customer_id = self.mou_id.nama_cust

        # # samakan currency dengan MOU
        # self.currency_id = self.mou_id.currency_id
        #
        # # hapus line lama
        # self.request_line_ids = [(5, 0, 0)]
        #
        # lines = []
        #
        # for line in self.mou_id.maklon_line_ids:
        #     vals = {
        #         'line_type': 'product',
        #         'product_id': line.product.id,
        #         'description': line.product.display_name,
        #         'product_qty': line.product_qty,
        #         'product_uom': line.uom_id.id,
        #         'price_unit': line.product_hna,
        #         'tax_ids': [(6, 0, line.tax_ids.ids)],
        #         'currency_id': self.mou_id.currency_id.id,
        #         'date_planned': line.date_estimasi,
        #     }
        #
        #     lines.append((0, 0, vals))
        #
        # self.request_line_ids = lines

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
        """Ajukan approval; PR baru jadi Purchase Request setelah disetujui."""
        for rec in self:
            if not rec.request_line_ids and not rec.item_line_ids:
                raise UserError('Isi minimal satu produk atau item setup sebelum diajukan.')
            rec.state = 'to_approve'
            rec.message_post(body='PR diajukan untuk approval.')

    def action_approve(self):
        if not self.env.user.has_group('custom_purchase_request.group_pr_approver'):
            raise UserError('Hanya PR Approver yang boleh menyetujui PR.')
        for rec in self.filtered(lambda r: r.state == 'to_approve'):
            rec.state = 'pr'
            rec.message_post(body=f'PR disetujui oleh {self.env.user.name}.')

    def action_reject(self):
        if not self.env.user.has_group('custom_purchase_request.group_pr_approver'):
            raise UserError('Hanya PR Approver yang boleh menolak PR.')
        for rec in self.filtered(lambda r: r.state == 'to_approve'):
            rec.state = 'draft'
            rec.message_post(body=f'PR dikembalikan ke Draft oleh {self.env.user.name}.')

    @api.onchange('purchase_purpose')
    def _onchange_purchase_purpose(self):
        if self.purchase_purpose == 'non_produksi':
            self.mou_id = False
            self.sale_order_id = False
            self.customer_id = False

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancelled'

    def action_set_draft(self):
        for rec in self:
            rec.state = 'draft'

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
                    'mou_id': self.mou_id.id,
                    'sale_order_id': self.sale_order_id.id,
                }))
            if line.setup_item_id:
                lines.append((0, 0, {
                    'line_type': 'setup',
                    'setup_item_id': line.setup_item_id.id,
                    'quantity': line.item_qty,
                    'price_unit': 0.0,
                    'mou_id': self.mou_id.id,
                    'sale_order_id': self.sale_order_id.id,
                }))

        usulan = self.env['usulan.usulan.dana'].create({
            'department_id': self.department_id.id,
            # 'vendor_id': self.vendor_id.id,
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
    description = fields.Text(string='Description')
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

class PurchaseRequestBulkMOULine(models.Model):
    _name = 'purchase.request.bulk.mou.line'
    _description = 'Purchase Request Bulk Allocation'

    purchase_request_id = fields.Many2one(
        'purchase.request',
        required=True,
        ondelete='cascade'
    )

    mou_id = fields.Many2one(
        'draft.maklon',
        string='No. MOU',
        required=True
    )

    customer_id = fields.Many2one(
        related='mou_id.nama_cust',
        string='Customer',
        store=True,
        readonly=True
    )

    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True
    )

    qty = fields.Float(
        string='Allocated Qty',
        required=True,
        default=1
    )

    uom_id = fields.Many2one(
        'uom.uom',
        string='UoM',
        related='product_id.uom_id',
        store=True,
        readonly=True
    )

    note = fields.Char(
        string='Remarks'
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='purchase_request_id.currency_id',
        store=True,
        readonly=True,
    )

    price_unit = fields.Monetary(
        string='Unit Price',
        currency_field='currency_id',
    )

    price_subtotal = fields.Monetary(
        string='Subtotal',
        compute='_compute_subtotal',
        store=True,
        currency_field='currency_id',
    )

    @api.depends('qty', 'price_unit')
    def _compute_subtotal(self):
        for rec in self:
            rec.price_subtotal = rec.qty * rec.price_unit