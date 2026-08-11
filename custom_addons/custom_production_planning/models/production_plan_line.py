from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ProductionPlanLine(models.Model):
    _name = "mrp.production.plan.line"
    _description = "Production Planning Operation"
    _order = "sequence"

    sequence = fields.Integer(
        default=10,
    )

    plan_id = fields.Many2one(
        "mrp.production.plan",
        required=True,
        ondelete="cascade",
    )

    # Diambil dari BOM Operation
    operation_id = fields.Many2one(
        "mrp.routing.workcenter",
        string="Operation",
        required=True,
    )

    # Work Center otomatis dari Operation
    workcenter_id = fields.Many2one(
        "mrp.workcenter",
        related="operation_id.workcenter_id",
        store=True,
        readonly=True,
        string="Work Center",
    )

    # Dipilih oleh Production Planner
    machine_id = fields.Many2one(
        "mrp.production.machine",
        string="Machine",
        domain=[
            ('active', '=', True)
        ],
    )

    # Dipilih setelah machine
    capacity_id = fields.Many2one(
        "mrp.production.machine.capacity",
        string="Machine Capacity",
        domain="[('machine_id', '=', machine_id)]",
    )

    capacity_per_day = fields.Float(
        related="capacity_id.capacity_per_day",
        store=True,
    )

    planned_start = fields.Datetime(
        string="Production Start",
    )

    planned_end = fields.Datetime(
        string="Production End",
    )

    schedule_ids = fields.One2many(
        "mrp.production.machine.schedule",
        "plan_line_id",
        string="Machine Schedule",
    )

    state = fields.Selection([
        ("planned", "Planned"),
        ("running", "Running"),
        ("done", "Done"),
    ],
        compute="_compute_state",
        store=True,
    )

    workorder_id = fields.Many2one(
        "mrp.workorder",
        string="Work Order",
        compute="_compute_workorder",
        store=True,
    )

    capacity_warning = fields.Char(
        compute="_compute_capacity_warning"
    )

    @api.onchange("operation_id")
    def _onchange_operation(self):
        self.machine_id = False
        self.capacity_id = False

        recommendation = self._get_best_machine()

        if recommendation:
            self.machine_id = recommendation["machine"]
            self.capacity_id = recommendation["capacity"]


    @api.onchange("machine_id")
    def _onchange_machine_id(self):
        self.capacity_id = False


    @api.depends("schedule_ids.state")
    def _compute_state(self):
        for line in self:
            if line.schedule_ids:
                line.state = line.schedule_ids[0].state
            else:
                line.state = "planned"


    @api.depends("schedule_ids.workorder_id")
    def _compute_workorder(self):
        for line in self:
            schedule = line.schedule_ids[:1]
            line.workorder_id = schedule.workorder_id if schedule else False


    @api.constrains("operation_id", "machine_id")
    def _check_machine_workcenter(self):
        for rec in self:
            if (
                rec.machine_id
                and rec.workcenter_id
                and rec.machine_id.workcenter_id != rec.workcenter_id
            ):
                raise ValidationError(
                    "Selected machine does not belong to the operation's work center."
                )

    @api.onchange("workcenter_id")
    def _onchange_workcenter(self):
        self.machine_id = False
        self.capacity_id = False

        return {
            "domain": {
                "machine_id": [
                    (
                        "workcenter_id",
                        "=",
                        self.workcenter_id.id
                    ),
                    (
                        "active",
                        "=",
                        True
                    )
                ]
            }
        }

    @api.depends(
        "machine_id",
        "capacity_id"
    )
    def _compute_capacity_warning(self):
        for line in self:
            line.capacity_warning = False

            if not line.machine_id:
                continue

            if not line.capacity_id:
                continue

            if line.capacity_id.capacity_per_day <= 0:
                line.capacity_warning = (
                    "Invalid capacity"
                )

    def _get_best_machine(self):
        self.ensure_one()

        Machine = self.env["mrp.production.machine"]
        Schedule = self.env["mrp.production.machine.schedule"]

        planning_date = self.plan_id.planned_start

        machines = Machine.search([
            ("active", "=", True),
            ("workcenter_id", "=", self.workcenter_id.id),
        ])

        best_machine = False
        best_capacity = False
        best_remaining = -1
        best_utilization = 999999

        for machine in machines:
            if not machine.capacity_ids:
                continue

            # pilih kapasitas terbesar milik mesin
            capacity = max(
                machine.capacity_ids,
                key=lambda c: c.capacity_per_day
            )

            # total qty yang sudah dijadwalkan pada tanggal tersebut
            existing_qty = sum(
                Schedule.search([
                    ("machine_id", "=", machine.id),
                    ("planned_start", "<=", planning_date),
                    ("planned_end", ">=", planning_date),
                    ("state", "!=", "done"),
                ]).mapped("planned_qty")
            )

            remaining = max(
                capacity.capacity_per_day - existing_qty,
                0
            )

            utilization = 0

            if capacity.capacity_per_day:
                utilization = (
                                  existing_qty /
                                  capacity.capacity_per_day
                              ) * 100

            # Prioritas:
            # 1. Remaining terbesar
            # 2. Utilization terkecil

            if (
                remaining > best_remaining
                or (
                remaining == best_remaining
                and utilization < best_utilization
            )
            ):
                best_machine = machine
                best_capacity = capacity
                best_remaining = remaining
                best_utilization = utilization

        if not best_machine:
            return False

        return {
            "machine": best_machine,
            "capacity": best_capacity,
        }

    @api.constrains(
        "machine_id",
        "capacity_id",
    )
    def _check_locked_plan(self):

        for line in self:

            if line.plan_id.state in (
                "approved",
                "running",
                "done",
            ):
                raise ValidationError(
                    "You cannot change machine or capacity after approval."
                )