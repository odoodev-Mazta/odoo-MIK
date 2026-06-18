from odoo import api, fields, models

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

    item_line_ids = fields.One2many(
        'purchase.order.line',
        'order_id',
        string='Item Setup'
    )

    setup_line_ids = fields.One2many(
        'purchase.order.setup.line',
        'order_id',
        string='Item Setup'
    )

    @api.onchange('mou_id')
    def _onchange_mou(self):
        if self.mou_id:
            self.customer_id = self.mou_id.nama_cust

    @api.onchange('customer_id')
    def _onchange_customer(self):
        self.mou_id = False

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