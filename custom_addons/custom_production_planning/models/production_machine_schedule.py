from odoo import api, fields, models
from odoo.exceptions import ValidationError

class ProductionMachineSchedule(models.Model):
    _name = "mrp.production.machine.schedule"

    name = fields.Char(
        string="Schedule Reference",
        compute="_compute_name",
        store=True,
    )

    plan_line_id = fields.Many2one(
        "mrp.production.plan.line",
        required=True,
        ondelete="cascade"
    )

    plan_id = fields.Many2one(
        "mrp.production.plan",
        related="plan_line_id.plan_id",
        store=True,
        string="Production Plan"
    )

    machine_id = fields.Many2one(
        "mrp.production.machine",
        required=True,
        ondelete="cascade"
    )

    capacity_id = fields.Many2one(
        "mrp.production.machine.capacity",
    )

    product_id = fields.Many2one(
        "product.product"
    )

    planned_start = fields.Date(
        required=True
    )

    planned_end = fields.Date(
        required=True
    )

    planned_qty = fields.Float(
        string="Planned Quantity"
    )

    state = fields.Selection(
        [
            ("planned", "Planned"),
            ("running", "Running"),
            ("done", "Done"),
        ],
        string="Status",
        compute="_compute_state",
        store=True,
    )

    operation_id = fields.Many2one(
        "mrp.routing.workcenter",
        string="Operation",
    )

    workorder_id = fields.Many2one(
        "mrp.workorder",
        string="Work Order"
    )

    schedule_sequence = fields.Integer(
        string="Schedule Sequence",
        default=1,
    )

    daily_qty = fields.Float(
        string="Daily Production Qty",
    )

    duration = fields.Float(
        string="Duration (Hours)",
        compute="_compute_duration",
        store=True,
    )

    @api.depends("workorder_id.state")
    def _compute_state(self):
        for schedule in self:

            if not schedule.workorder_id:
                schedule.state = "planned"
                continue

            wo_state = schedule.workorder_id.state

            if wo_state == "done":
                schedule.state = "done"

            elif wo_state in ("ready", "progress"):
                schedule.state = "running"

            else:
                schedule.state = "planned"

    @api.depends("planned_start", "planned_end")
    def _compute_duration(self):
        for rec in self:
            if rec.planned_start and rec.planned_end:
                delta = rec.planned_end - rec.planned_start
                rec.duration = delta.total_seconds() / 3600
            else:
                rec.duration = 0

    @api.depends(
        "product_id",
        "operation_id",
        "machine_id",
    )
    def _compute_name(self):
        for rec in self:
            rec.name = "%s - %s - %s" % (
                rec.product_id.display_name or "",
                rec.operation_id.name or "",
                rec.machine_id.name or "",
            )