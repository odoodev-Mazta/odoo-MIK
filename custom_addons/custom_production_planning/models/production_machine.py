from odoo import api, fields, models
from odoo.exceptions import ValidationError

class ProductionMachine(models.Model):
    _name = "mrp.production.machine"
    _description = "Production Machine"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(
        required=True,
        tracking=True,
    )

    code = fields.Char(
        required=True,
        tracking=True,
    )

    workcenter_id = fields.Many2one(
        "mrp.workcenter",
        string="Work Center",
    )

    operator_count = fields.Integer(
        string="Number of Operators",
        default=1,
    )

    active = fields.Boolean(
        default=True,
    )

    note = fields.Text()

    capacity_ids = fields.One2many(
        "mrp.production.machine.capacity",
        "machine_id",
        string="Capacity Configuration",
    )

    machine_schedule_ids = fields.One2many(
        "mrp.production.machine.schedule",
        "machine_id",
    )

    schedule_ids = fields.One2many(
        "mrp.production.machine.schedule",
        "machine_id",
        string="Machine Schedule"
    )

    utilization = fields.Float(
        string="Utilization (%)",
        compute="_compute_utilization",
        store=False,
    )

    planned_qty = fields.Float(
        string="Planned Qty",
        compute="_compute_utilization",
        store=False,
    )

    capacity_today = fields.Float(
        string="Capacity",
        compute="_compute_utilization",
        store=False,
    )

    utilization_state = fields.Selection(
        [
            ("available", "Available"),
            ("busy", "Busy"),
            ("near", "Near Capacity"),
            ("over", "Over Capacity"),
        ],
        compute="_compute_utilization",
        store=False,
    )

    remaining_capacity = fields.Float(
        string="Remaining Capacity",
        compute="_compute_utilization",
        store=False,
    )

    available_capacity_today = fields.Float(
        string="Available Capacity Today",
        compute="_compute_utilization",
    )

    @api.constrains("code")
    def _check_code(self):
        for rec in self:
            if self.search_count([
                ("id", "!=", rec.id),
                ("code", "=", rec.code),
            ]):
                raise ValidationError(
                    "Machine code must be unique."
                )

    @api.depends(
        "schedule_ids",
        "schedule_ids.planned_qty",
        "schedule_ids.planned_start",
        "schedule_ids.planned_end",
    )
    def _compute_utilization(self):
        today = fields.Date.today()

        Schedule = self.env[
            "mrp.production.machine.schedule"
        ]

        for machine in self:

            schedules = Schedule.search([
                (
                    "machine_id",
                    "=",
                    machine.id
                ),
                (
                    "planned_start",
                    "<=",
                    today
                ),
                (
                    "planned_end",
                    ">=",
                    today
                ),
                (
                    "state",
                    "!=",
                    "done"
                ),
            ])

            planned_qty = sum(
                schedules.mapped(
                    "planned_qty"
                )
            )

            # cari kapasitas aktif
            capacity = 0

            if machine.capacity_ids:
                capacity = max(
                    machine.capacity_ids.mapped(
                        "capacity_per_day"
                    )
                )

            utilization = 0

            if capacity:
                utilization = (
                              planned_qty /
                              capacity
                              ) * 100
            machine.planned_qty = planned_qty
            machine.capacity_today = capacity
            machine.utilization = utilization
            if utilization > 100:
                machine.utilization_state = "over"
            elif utilization >= 90:
                machine.utilization_state = "near"
            elif utilization >= 70:
                machine.utilization_state = "busy"
            else:
                machine.utilization_state = "available"