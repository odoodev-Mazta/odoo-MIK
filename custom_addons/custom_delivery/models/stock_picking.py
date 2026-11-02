from odoo import models, fields, api


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    mou_id = fields.Many2one(
        'draft.maklon',
        string='No MOU',
        compute='_compute_mou_id',
        store=True,
        readonly=False,
        domain="[('nama_cust', '=', partner_id), ('state', '=', 'mou')]",
    )

    delivery_line_ids = fields.One2many(
        'stock.picking.delivery.line',
        'picking_id',
        string='Deliveries'
    )

    is_return =fields.Boolean(
        string='Is Return',
        compute='_compute_is_return',
        store=True,
    )

    @api.depends('move_ids.origin_returned_move_id')
    def _compute_is_return(self):
        for picking in self:
            picking.is_return = bool(picking.move_ids.mapped('origin_returned_move_id'))

    @api.depends('sale_id.mou_id')
    def _compute_mou_id(self):
        for picking in self:
            picking.mou_id = picking.sale_id.mou_id or picking.mou_id

    @api.onchange('partner_id')
    def _onchange_partner_id_delivery(self):
        if self.sale_id:
            return
        self.mou_id = False
        self.delivery_line_ids = [(5, 0, 0)]

    @api.onchange('mou_id')
    def _onchange_mou_id(self):
        # Delivery dari SO: barisnya milik SO, jangan diganti dari MOU.
        if self.sale_id:
            return
        self.delivery_line_ids = [(5, 0, 0)]
        self.move_ids = [(5, 0, 0)]

        if not self.mou_id:
            return

        delivery_lines = []
        move_lines = []

        for line in self.mou_id.maklon_line_ids:
            delivery_lines.append((0, 0, {
                'product_id': line.product.id,
                'product_qty': line.product_qty,
                'uom_id': line.uom_id.id,
                'date_estimasi': line.date_estimasi,
                'jenis_product': line.jenis_product,
                'kemasan': line.kemasan,
                'ukuran': line.ukuran,
                'product_hna': line.product_hna,
                'diskon': line.diskon,
                'total_value': line.total_value,
            }))

            move_lines.append((0, 0, {
                'product_id': line.product.id,
                'product_uom_qty': line.product_qty,
                'product_uom': line.uom_id.id,
                'location_id': self.location_id.id,
                'location_dest_id': self.location_dest_id.id,
                'date_estimasi': line.date_estimasi,
                'jenis_product': line.jenis_product,
                'kemasan': line.kemasan,
                'ukuran': line.ukuran,
                'product_hna': line.product_hna,
                'diskon': line.diskon,
            }))

        self.delivery_line_ids = delivery_lines
        self.move_ids = move_lines