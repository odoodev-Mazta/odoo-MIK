from odoo import fields, models, tools


class PurchaseRequestReport(models.Model):
    _name = 'purchase.request.report'
    _description = 'Purchase Request Report'
    _auto = False
    _rec_name = 'name'

    # HEADER PURCHASE REQUEST

    request_id = fields.Many2one(
        'purchase.request',
        string='Purchase Request'
    )

    name = fields.Char(
        string='PR Number'
    )

    department_id = fields.Many2one(
        'hr.department',
        string='Department'
    )

    vendor_id = fields.Many2one(
        'res.partner',
        string='Vendor'
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
    ], string='Status')

    date_usulan = fields.Datetime(
        string='Request Date'
    )

    estimated_date = fields.Date(
        string='Needed Date'
    )

    is_urgent = fields.Boolean(
        string='Urgent'
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency'
    )

    total_amount = fields.Monetary(
        string='Total Amount'
    )

    total_qty = fields.Float(
        string='Total Qty'
    )

    # LINE PURCHASE REQUEST

    line_id = fields.Many2one(
        'purchase.request.line',
        string='Line'
    )

    product_id = fields.Many2one(
        'product.product',
        string='Product'
    )

    description = fields.Text(
        string='Description'
    )

    qty = fields.Float(
        string='Qty'
    )

    product_uom = fields.Many2one(
        'uom.uom',
        string='UoM'
    )

    price_unit = fields.Float(
        string='Unit Price'
    )

    subtotal = fields.Monetary(
        string='Subtotal'
    )

    date_planned = fields.Date(
        string='Planned Date'
    )

    # =========================================
    # SQL VIEW
    # =========================================

    def init(self):

        tools.drop_view_if_exists(
            self.env.cr,
            self._table
        )

        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (

                SELECT

                    -- PRIMARY ID
                    l.id AS id,

                    -- HEADER
                    r.id AS request_id,
                    r.name AS name,
                    r.department_id AS department_id,
                    r.vendor_id AS vendor_id,
                    r.state AS state,
                    r.create_date AS date_usulan,
                    r.estimated_date AS estimated_date,
                    r.is_urgent AS is_urgent,
                    r.currency_id AS currency_id,
                    r.total_amount AS total_amount,
                    r.total_qty AS total_qty,

                    -- LINE
                    l.id AS line_id,
                    l.product_id AS product_id,
                    l.name AS description,
                    l.product_qty AS qty,
                    l.product_uom AS product_uom,
                    l.price_unit AS price_unit,
                    l.price_subtotal AS subtotal,
                    l.date_planned AS date_planned

                FROM purchase_request_line l

                INNER JOIN purchase_request r
                    ON r.id = l.request_id

            )
        """)