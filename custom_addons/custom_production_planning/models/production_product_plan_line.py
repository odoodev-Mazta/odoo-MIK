from odoo import api, fields, models
from odoo.exceptions import ValidationError

class ProductionPlanProductLine(models.Model):
    _name = "mrp.production.plan.product.line"
    _description = "Production Planning Product"
    _order = "sequence, id"
    _rec_name = "product_id"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    sequence = fields.Integer(
        string="Sequence",
        default=10,
    )

    plan_id = fields.Many2one(
        "mrp.production.plan",
        string="Production Plan",
        required=True,
        ondelete="cascade",
    )

    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
    )

    product_qty = fields.Float(
        string="Quantity",
        required=True,
    )

    production_qty = fields.Float(
        string="Production Quantity",
        compute="_compute_production_qty",
        store=True,
    )

    production_start = fields.Date(
        string="Production Start",
    )

    production_end = fields.Date(
        string="Production End",
    )

    production_number = fields.Char(
        string="No. Produksi",
        readonly=True,
        copy=False,
    )

    product_uom_id = fields.Many2one(
        "uom.uom",
        related="product_id.uom_id",
        store=True,
        readonly=True,
        string="UoM",
    )

    operation_line_ids = fields.One2many(
        "mrp.production.plan.line",
        "product_line_id",
        string="Operations",
    )

    manufacturing_order_ids = fields.One2many(
        "mrp.production",
        "production_plan_product_line_id",
        string="Manufacturing Orders",
    )

    progress = fields.Float(
        string="Progress",
        compute="_compute_progress",
        store=True,
    )

    parent_product_line_id = fields.Many2one(
        "mrp.production.plan.product.line",
        string="Parent Product",
        readonly=True,
        copy=False,
        ondelete="cascade",
    )

    child_product_line_ids = fields.One2many(
        "mrp.production.plan.product.line",
        "parent_product_line_id",
        string="Split Productions",
    )

    is_child_product_line = fields.Boolean(
        string="Is Split Production",
        compute="_compute_is_child_product_line",
        store=True,
    )

    has_child_production = fields.Boolean(
        string="Has Split Production",
        compute="_compute_has_child_production",
        store=True,
    )

    child_allocated_qty = fields.Float(
        string="Allocated Split Quantity",
        compute="_compute_child_quantities",
        store=True,
    )

    remaining_qty = fields.Float(
        string="Remaining Quantity",
        compute="_compute_child_quantities",
        store=True,
    )

    production_type = fields.Selection(
        [
            ("main", "Main Production"),
            ("split", "Production Split"),
            ("partial", "Partial Production"),
        ],
        string="Production Type",
        compute="_compute_production_type",
        store=True,
    )

    create_mo = fields.Boolean(
        string="Create MO",
        default=False,
        readonly=False,
    )

    has_mo = fields.Boolean(
        string="MO Created",
        compute="_compute_has_mo",
        store=True,
    )

    @api.depends("manufacturing_order_ids")
    def _compute_has_mo(self):
        for line in self:
            line.has_mo = bool(line.manufacturing_order_ids)

    @api.constrains("product_qty")
    def _check_product_qty(self):
        for line in self:
            if line.product_qty <= 0:
                raise ValidationError(
                    "Production quantity must be greater than zero."
                )

    @api.depends(
        "manufacturing_order_ids",
        "manufacturing_order_ids.workorder_ids",
        "manufacturing_order_ids.workorder_ids.state",
    )
    def _compute_progress(self):
        for line in self:
            workorders = line.manufacturing_order_ids.mapped(
                "workorder_ids"
            )

            if not workorders:
                line.progress = 0
                continue

            done = workorders.filtered(
                lambda wo: wo.state == "done"
            )

            line.progress = (
                len(done) / len(workorders)
            ) * 100

    @api.depends("parent_product_line_id")
    def _compute_is_child_product_line(self):
        for line in self:
            line.is_child_product_line = bool(
                line.parent_product_line_id
            )

    @api.depends("child_product_line_ids")
    def _compute_has_child_production(self):
        for line in self:
            line.has_child_production = bool(
                line.child_product_line_ids
            )

    @api.depends(
        "product_qty",
        "child_product_line_ids.product_qty",
    )
    def _compute_production_qty(self):
        for line in self:
            if line.child_product_line_ids:
                line.production_qty = line.remaining_qty
            else:
                line.production_qty = line.product_qty

    @api.depends(
        "product_qty",
        "child_product_line_ids.product_qty",
    )
    def _compute_child_quantities(self):
        for line in self:

            allocated = sum(
                line.child_product_line_ids.mapped(
                    "product_qty"
                )
            )

            line.child_allocated_qty = allocated

            line.remaining_qty = max(
                line.product_qty - allocated,
                0,
            )

    @api.depends(
        "parent_product_line_id",
        "child_product_line_ids",
    )
    def _compute_production_type(self):
        for line in self:

            if line.parent_product_line_id:
                line.production_type = "partial"

            elif line.child_product_line_ids:
                line.production_type = "split"

            else:
                line.production_type = "main"

    def action_open_split_wizard(self):
        self.ensure_one()

        plan = self.plan_id

        if plan.state != "draft":
            raise ValidationError(
                "Production cannot be split after planning "
                "has been scheduled or approved."
            )

        if plan.capacity_checked:
            raise ValidationError(
                "Production cannot be split after machine "
                "schedule has been generated."
            )

        if self.parent_product_line_id:
            raise ValidationError(
                "Production Product hasil split tidak dapat "
                "di-split lagi."
            )

        if self.manufacturing_order_ids:
            raise ValidationError(
                "Production tidak dapat di-split karena "
                "Manufacturing Order sudah dibuat."
            )

        if self.remaining_qty <= 0:
            raise ValidationError(
                "Tidak ada quantity yang tersisa untuk di-split."
            )

        return {
            "type": "ir.actions.act_window",
            "name": "Partial Production",
            "res_model": "mrp.production.plan.split.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_product_line_id": self.id,
            },
        }

    def action_view_child_productions(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Partial Productions",
            "res_model": "mrp.production.plan.product.line",
            "view_mode": "list,form",
            "domain": [
                ("parent_product_line_id", "=", self.id),
            ],
            "context": {
                "default_parent_product_line_id": self.id,
                "default_plan_id": self.plan_id.id,
                "default_product_id": self.product_id.id,
            },
        }