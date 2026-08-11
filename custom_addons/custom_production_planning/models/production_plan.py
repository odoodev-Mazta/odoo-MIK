from odoo import api, fields, models
from odoo.exceptions import ValidationError
from datetime import timedelta
import math

class ProductionPlan(models.Model):
    _name = "mrp.production.plan"
    _description = "Production Planning"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "planned_start desc"

    name = fields.Char(
        default="New",
        readonly=True,
        copy=False,
        tracking=True,
    )

    sale_order_id = fields.Many2one(
        "sale.order",
        required=True,
        tracking=True,
    )

    customer_id = fields.Many2one(
        related="sale_order_id.partner_id",
        store=True,
    )

    planned_start = fields.Date(
        required=True,
        tracking=True,
    )

    planned_end = fields.Date(
        required=True,
        tracking=True,
    )

    state = fields.Selection([
        ("draft", "Draft"),
        ("planned", "Planned"),
        ("approved", "Approved"),
        ("running", "Running"),
        ("done", "Done"),
        ("cancel", "Cancelled"),
    ],
        default="draft",
        tracking=True,
        string="Status",
    )

    note = fields.Text()

    line_ids = fields.One2many(
        "mrp.production.plan.line",
        "plan_id",
    )

    machine_schedule_ids = fields.One2many(
        "mrp.production.machine.schedule",
        "plan_id",
        string="Machine Schedule",
    )

    manufacturing_order_ids = fields.One2many(
        "mrp.production",
        "production_plan_id",
        string="Manufacturing Orders"
    )

    product_id = fields.Many2one(
        "product.product",
        required=True,
        string="Product",
    )

    product_qty = fields.Float(
        required=True,
        string="Quantity",
    )

    product_uom_id = fields.Many2one(
        "uom.uom",
        related="product_id.uom_id",
        store=True,
    )

    progress = fields.Float(
        string="Progress",
        compute="_compute_progress",
        store=True,
    )

    capacity_checked = fields.Boolean(
        string="Capacity Checked",
        default=False,
    )

    material_checked = fields.Boolean(
        string="Material Checked",
        default=False,
    )

    material_status = fields.Selection(
        [
            ("not_checked", "Not Checked"),
            ("available", "Available"),
            ("shortage", "Material Shortage"),
        ],
        default="not_checked",
        string="Material Status",
    )

    material_check_state = fields.Selection(
        [
            ("not_checked", "Not Checked"),
            ("available", "Available"),
            ("shortage", "Shortage Found"),
        ],
        default="not_checked",
        tracking=True,
    )

    material_shortage_ids = fields.One2many(
        "mrp.production.material.shortage",
        "plan_id",
        string="Material Shortage"
    )

    def action_approve(self):

        self.action_validate_planning()

        for plan in self:

            if plan.material_check_state != "available":
                raise ValidationError(
                    "Please check material availability first."
                )

            plan.state = "approved"

        return True

    def _get_available_capacity(
            self,
            machine,
            capacity,
            schedule_date
    ):
        Schedule = self.env[
            "mrp.production.machine.schedule"
        ]

        schedules = Schedule.search([
            (
                "machine_id",
                "=",
                machine.id
            ),
            (
                "planned_start",
                "=",
                schedule_date
            ),
            (
                "state",
                "!=",
                "done"
            ),
        ])
        used_qty = sum(
            schedules.mapped(
                "planned_qty"
            )
        )
        return max(
            capacity - used_qty,
            0
        )

    def action_check_capacity(self):
        Schedule = self.env[
            "mrp.production.machine.schedule"
        ]

        for plan in self:
            if not plan.product_id:
                raise ValidationError(
                    "Please select product first."
                )

            if not plan.planned_start:
                raise ValidationError(
                    "Please set production planning start date."
                )

            if not plan.line_ids:
                raise ValidationError(
                    "Please load BOM operations first."
                )

            # hapus schedule lama
            plan.machine_schedule_ids.unlink()

            current_start = plan.planned_start
            latest_end = current_start

            lines = plan.line_ids.sorted(
                key=lambda x: x.sequence
            )

            for line in lines:
                if not line.machine_id:
                    raise ValidationError(
                        f"Please assign machine for "
                        f"{line.operation_id.name}"
                    )

                if (
                    line.machine_id.workcenter_id
                    != line.operation_id.workcenter_id
                ):
                    raise ValidationError(
                        f"""
                        Machine {line.machine_id.name}
                        is not compatible with
                        {line.operation_id.name}
                        """
                    )

                if not line.capacity_id:
                    raise ValidationError(
                        f"Please assign capacity for "
                        f"{line.operation_id.name}"
                    )

                capacity = (
                    line.capacity_id.capacity_per_day
                )

                if capacity <= 0:
                    raise ValidationError(
                        f"""
                        Invalid capacity for
                        {line.machine_id.name}
                        """
                    )

                remaining_qty = plan.product_qty
                schedule_date = current_start

                sequence = 1

                while remaining_qty > 0:

                    # cek kapasitas kosong hari tersebut
                    available_capacity = (
                        self._get_available_capacity(
                            line.machine_id,
                            capacity,
                            schedule_date
                        )
                    )

                    # mesin penuh, pindah hari
                    if available_capacity <= 0:
                        schedule_date += timedelta(
                            days=1
                        )

                        continue

                    # qty yang bisa masuk hari ini
                    daily_qty = min(
                        available_capacity,
                        remaining_qty
                    )

                    Schedule.create({
                        "plan_id": plan.id,
                        "plan_line_id": line.id,
                        "operation_id": line.operation_id.id,
                        "machine_id": line.machine_id.id,
                        "capacity_id": line.capacity_id.id,
                        "product_id": plan.product_id.id,
                        "planned_qty": daily_qty,
                        "daily_qty": daily_qty,
                        "schedule_sequence": sequence,
                        "planned_start": schedule_date,
                        "planned_end": schedule_date,
                    })

                    remaining_qty -= daily_qty
                    sequence += 1

                    # update tanggal
                    if remaining_qty > 0:
                        schedule_date += timedelta(
                            days=1
                        )

                # cari schedule terakhir operation ini

                last_schedule = Schedule.search(
                    [
                        (
                            "plan_line_id",
                            "=",
                            line.id
                        )
                    ],
                    order="planned_end desc",
                    limit=1
                )

                if last_schedule:
                    # operation berikutnya bisa mulai
                    # di hari yang sama
                    current_start = (
                        last_schedule.planned_end
                    )

                    if (
                            last_schedule.planned_end
                            >
                            latest_end
                    ):
                        latest_end = (
                            last_schedule.planned_end
                        )

            plan.planned_end = latest_end
            plan.capacity_checked = True
            plan.state = "planned"
        return True

    def action_create_mo(self):
        Production = self.env["mrp.production"]

        for plan in self:
            if plan.state != "approved":
                raise ValidationError(
                    "Planning must be approved first."
                )

            if plan.manufacturing_order_ids:
                raise ValidationError(
                    "Manufacturing Order has already been created "
                    "for this planning."
                )

            if not plan.product_id:
                raise ValidationError(
                    "Production Plan has no product."
                )

            if not plan.product_qty or plan.product_qty <= 0:
                raise ValidationError(
                    "Production Plan has an invalid quantity."
                )

            if not plan.line_ids:
                raise ValidationError(
                    "Production Plan has no operation."
                )

            if not plan.machine_schedule_ids:
                raise ValidationError(
                    "No machine schedule found."
                )

            bom = self.env["mrp.bom"].search([
                (
                    "product_tmpl_id",
                    "=",
                    plan.product_id.product_tmpl_id.id
                )
            ], limit=1)

            if not bom:
                raise ValidationError(
                    f"No Bill of Materials found for "
                    f"{plan.product_id.display_name}."
                )

            vals = {
                "product_id": plan.product_id.id,
                "product_qty": plan.product_qty,
                "product_uom_id": plan.product_id.uom_id.id,
                "bom_id": bom.id,
                "production_plan_id": plan.id,
            }

            mo = Production.create(vals)
            mo.action_confirm()

            if not mo.workorder_ids:
                raise ValidationError(
                    "Manufacturing Order was created, "
                    "but no Work Orders were generated."
                )

            schedules = self.env[
                "mrp.production.machine.schedule"
            ].search([
                (
                    "plan_line_id.plan_id",
                    "=",
                    plan.id
                )
            ])

            for schedule in schedules:
                workorder = mo.workorder_ids.filtered(
                    lambda w:
                    w.operation_id == schedule.operation_id
                )

                if workorder:
                    schedule.workorder_id = workorder[0].id

            plan.state = "running"

        return True

    def action_load_operations(self):
        OperationLine = self.env[
            "mrp.production.plan.line"
        ]

        for plan in self:

            if not plan.product_id:
                raise ValidationError(
                    "Please select product first."
                )

            bom = self.env["mrp.bom"].search([
                (
                    "product_tmpl_id",
                    "=",
                    plan.product_id.product_tmpl_id.id
                )
            ], limit=1)

            if not bom:
                raise ValidationError(
                    "BOM not found for this product."
                )

            # Hapus operation lama
            plan.line_ids.unlink()
            vals = []

            for index, operation in enumerate(
                    bom.operation_ids,
                    start=1
            ):
                vals.append({
                    "plan_id": plan.id,
                    "operation_id": operation.id,
                    "sequence": index * 10,
                })
            OperationLine.create(vals)

        return True

    def action_reschedule(self):
        for plan in self:
            if plan.state in ("running", "done"):
                raise ValidationError(
                    "Running production cannot be rescheduled."
                )

            old_start = plan.planned_start
            old_end = plan.planned_end

            plan.machine_schedule_ids.unlink()

            plan.action_check_capacity()

            plan.message_post(
                body=(
                    f"""
                    Production Plan rescheduled.<br/>
                    Old Schedule :
                    {old_start} - {old_end}<br/>
                    New Schedule :
                    {plan.planned_start} - {plan.planned_end}
                    """
                )
            )

        return True

    @api.depends(
        "manufacturing_order_ids",
        "manufacturing_order_ids.workorder_ids",
        "manufacturing_order_ids.workorder_ids.state",
    )
    def _compute_progress(self):
        for plan in self:
            workorders = plan.manufacturing_order_ids.mapped(
                "workorder_ids"
            )

            if not workorders:
                plan.progress = 0
                continue

            done = workorders.filtered(
                lambda wo: wo.state == "done"
            )

            plan.progress = (
                len(done) /
                len(workorders)
            ) * 100

            # Semua Work Order selesai
            if (
                plan.state == "running"
                and len(done) == len(workorders)
            ):
                plan.state = "done"

    def action_check_machine_availability(self):
        Schedule = self.env[
            "mrp.production.machine.schedule"
        ]

        for plan in self:
            for line in plan.line_ids:
                if not line.machine_id:
                    raise ValidationError(
                        f"""
                        Machine not assigned for
                        {line.operation_id.name}
                        """
                    )

                capacity = (
                    line.capacity_id.capacity_per_day
                )

                qty_used = sum(
                    Schedule.search([
                        (
                            "machine_id",
                            "=",
                            line.machine_id.id
                        ),
                        (
                            "planned_start",
                            "=",
                            plan.planned_start
                        )
                    ]).mapped(
                        "planned_qty"
                    )
                )

                if qty_used >= capacity:
                    raise ValidationError(
                        f"""
                        Machine {line.machine_id.name}
                        is already full.
                        """
                    )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Available",
                "message":
                    "All machines are available.",
                "type": "success",
            }
        }

    def action_reset_planning(self):
        for plan in self:
            plan.machine_schedule_ids.unlink()
            plan.material_shortage_ids.unlink()

            plan.capacity_checked = False
            plan.material_checked = False
            plan.material_check_state = "not_checked"

            plan.state = "draft"

        return True

    def action_validate_planning(self):
        for plan in self:
            errors = []

            # BASIC VALIDATION
            if not plan.product_id:
                errors.append(
                    "• Product is empty."
                )

            if not plan.product_qty or plan.product_qty <= 0:
                errors.append(
                    "• Production quantity must be greater than zero."
                )

            if not plan.planned_start:
                errors.append(
                    "• Planning start date is empty."
                )

            if not plan.line_ids:
                errors.append(
                    "• No BOM operations loaded."
                )

            # CAPACITY VALIDATION
            if not plan.capacity_checked:
                errors.append(
                    "• Machine capacity has not been checked."
                )

            if not plan.machine_schedule_ids:
                errors.append(
                    "• Machine capacity planning has not been generated."
                )

            # MATERIAL VALIDATION
            if not plan.material_checked:
                errors.append(
                    "• Material availability has not been checked."
                )

            elif plan.material_check_state == "shortage":
                errors.append(
                    "• Material shortage found. "
                    "Please resolve material shortage before approval."
                )

            # BOM VALIDATION
            bom = False
            if plan.product_id:
                bom = self.env["mrp.bom"].search([
                    (
                        "product_tmpl_id",
                        "=",
                        plan.product_id.product_tmpl_id.id,
                    )
                ], limit=1)

            if not bom:
                errors.append(
                    "• BOM not found."
                )

            # PROCESS VALIDATION
            for line in plan.line_ids:

                operation_name = (
                        line.operation_id.name
                        or "Unknown Operation"
                )

                if not line.machine_id:
                    errors.append(
                        f"• {operation_name}: Machine not assigned."
                    )

                if not line.capacity_id:
                    errors.append(
                        f"• {operation_name}: Capacity not assigned."
                    )

                if line.capacity_per_day <= 0:
                    errors.append(
                        f"• {operation_name}: Invalid capacity."
                    )

                if not line.schedule_ids:
                    errors.append(
                        f"• {operation_name}: "
                        "Machine schedule not generated."
                    )

            # FINAL VALIDATION
            if errors:
                raise ValidationError(
                    "Planning Validation Failed\n\n"
                    + "\n".join(errors)
                )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Validation Success",
                "message": (
                    "Production Planning is valid "
                    "and ready for approval."
                ),
                "type": "success",
                "sticky": False,
            },
        }

    def action_check_material(self):
        for plan in self:
            plan.material_shortage_ids.unlink()

            plan.material_checked = False
            plan.material_check_state = "not_checked"

            # BASIC VALIDATION
            if not plan.product_id:
                raise ValidationError(
                    "Please select product first."
                )

            if not plan.product_qty or plan.product_qty <= 0:
                raise ValidationError(
                    "Please set a valid production quantity."
                )

            # FIND BOM
            bom = self.env["mrp.bom"].search([
                (
                    "product_tmpl_id",
                    "=",
                    plan.product_id.product_tmpl_id.id
                )
            ], limit=1)

            if not bom:
                raise ValidationError(
                    "BOM not found."
                )

            # CHECK MATERIAL
            material_lines = []
            has_shortage = False

            for bom_line in bom.bom_line_ids:
                material = bom_line.product_id

                required_qty = (
                        bom_line.product_qty
                        * plan.product_qty
                        / bom.product_qty
                )

                available_qty = material.qty_available

                shortage_qty = (
                        required_qty
                        - available_qty
                )

                # Jika shortage
                if shortage_qty > 0:
                    has_shortage = True

                material_lines.append({
                    "plan_id": plan.id,
                    "product_id": material.id,
                    "required_qty": required_qty,
                    "available_qty": available_qty,
                    "shortage_qty": max(shortage_qty, 0),
                })

            # SAVE MATERIAL RESULT
            if material_lines:
                self.env[
                    "mrp.production.material.shortage"
                ].create(material_lines)

            # UPDATE STATUS
            plan.material_checked = True
            if has_shortage:
                plan.material_check_state = "shortage"
            else:
                plan.material_check_state = "available"

        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }