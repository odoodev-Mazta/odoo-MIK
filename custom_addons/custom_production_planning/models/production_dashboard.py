from odoo import fields, models, tools

class ProductionDashboard(models.Model):
    _name = "mrp.production.dashboard"
    _description = "Production Dashboard"
    _auto = False
    _rec_name = "mo_name"
    _order = "planned_start desc, mo_name"

    mo_name = fields.Char(
        string="MO Number",
        readonly=True,
    )

    product_id = fields.Many2one(
        "product.product",
        string="Product",
        readonly=True,
    )

    customer_id = fields.Many2one(
        "res.partner",
        string="Customer",
        readonly=True,
    )

    production_plan_id = fields.Many2one(
        "mrp.production.plan",
        string="Production Plan",
        readonly=True,
    )

    product_qty = fields.Float(
        string="Quantity",
        readonly=True,
    )

    planned_start = fields.Date(
        string="Planned Start",
        readonly=True,
    )

    planned_end = fields.Date(
        string="Planned End",
        readonly=True,
    )

    current_workorder = fields.Char(
        string="Current Work Order",
        readonly=True,
    )

    next_workorder = fields.Char(
        string="Next Progress",
        readonly=True,
    )

    workorder_progress = fields.Float(
        string="Progress",
        readonly=True,
    )

    workorder_status = fields.Selection([
        ("pending", "Pending"),
        ("progress", "In Progress"),
        ("done", "Done"),
    ],
        string="Work Order Status",
        readonly=True,
    )

    state = fields.Selection([
        ("draft", "Draft"),
        ("confirmed", "Confirmed"),
        ("progress", "In Progress"),
        ("to_close", "To Close"),
        ("done", "Done"),
        ("cancel", "Cancelled"),
    ],
        string="MO Status",
        readonly=True,
    )

    def init(self):
        tools.drop_view_if_exists(
            self.env.cr,
            self._table,
        )

        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (

                SELECT
                    mp.id AS id,
                    mp.name AS mo_name,
                    mp.product_id AS product_id,
                    mp.product_qty AS product_qty,
                    mp.state AS state,
                    mp.production_plan_id AS production_plan_id,
                    
                    pp.customer_id AS customer_id,
                    pp.planned_start AS planned_start,
                    pp.planned_end AS planned_end,

                    current_wo.name AS current_workorder,
                    next_wo.name AS next_workorder,

                    COALESCE(
                        wo_progress.progress,
                        0
                    ) AS workorder_progress,

                    CASE
                        WHEN current_wo.state = 'progress'
                            THEN 'progress'

                        WHEN current_wo.state = 'done'
                            THEN 'done'

                        ELSE 'pending'
                    END AS workorder_status

                FROM mrp_production mp

                LEFT JOIN mrp_production_plan pp
                    ON pp.id = mp.production_plan_id

                LEFT JOIN LATERAL (

                    SELECT
                        wo.name,
                        wo.state,
                        wo.sequence
                    FROM mrp_workorder wo
                    WHERE wo.production_id = mp.id
                      AND wo.state = 'progress'
                    ORDER BY wo.sequence
                    LIMIT 1

                ) current_wo
                    ON TRUE

                LEFT JOIN LATERAL (

                    SELECT
                        wo.name,
                        wo.sequence
                    FROM mrp_workorder wo
                    WHERE wo.production_id = mp.id
                      AND wo.state IN (
                          'pending',
                          'ready'
                      )
                    ORDER BY wo.sequence
                    LIMIT 1

                ) next_wo
                    ON TRUE

                LEFT JOIN LATERAL (

                    SELECT
                        COUNT(*) FILTER (
                            WHERE wo.state = 'done'
                        ) * 100.0
                        / NULLIF(COUNT(*), 0)
                        AS progress

                    FROM mrp_workorder wo

                    WHERE wo.production_id = mp.id

                ) wo_progress
                    ON TRUE
            )
        """ % self._table)