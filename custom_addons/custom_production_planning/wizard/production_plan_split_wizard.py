from datetime import timedelta

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ProductionPlanSplitWizard(models.TransientModel):
    _name = "mrp.production.plan.split.wizard"
    _description = "Split Production Product"

    product_line_id = fields.Many2one(
        "mrp.production.plan.product.line",
        string="Production Product",
        required=True,
        readonly=True,
    )

    production_number = fields.Char(
        string="No. PO Produksi",
        related="product_line_id.plan_id.production_po_number",
        readonly=True,
    )

    product_id = fields.Many2one(
        "product.product",
        string="Product",
        related="product_line_id.product_id",
        readonly=True,
    )

    production_start = fields.Date(
        string="Production Start",
        required=True,
    )

    production_end = fields.Date(
        string="Production End",
        required=True,
    )

    total_qty = fields.Float(
        string="Total Quantity",
        related="product_line_id.product_qty",
        readonly=True,
    )

    allocated_qty = fields.Float(
        string="Allocated Quantity",
        related="product_line_id.child_allocated_qty",
        readonly=True,
    )

    remaining_qty = fields.Float(
        string="Remaining Quantity",
        related="product_line_id.remaining_qty",
        readonly=True,
    )

    split_qty = fields.Float(
        string="Quantity to Split",
        required=True,
    )

    @api.onchange("product_line_id")
    def _onchange_product_line_id(self):
        if self.product_line_id:
            self.production_start = (
                self.product_line_id.production_start
                or self.product_line_id.plan_id.planned_start
            )

            self.production_end = (
                self.product_line_id.production_end
                or self.product_line_id.plan_id.planned_end
            )

    @api.constrains("production_start", "production_end")
    def _check_production_dates(self):
        for wizard in self:
            if (
                wizard.production_start
                and wizard.production_end
                and wizard.production_end < wizard.production_start
            ):
                raise ValidationError(
                    "Production End must be greater than or equal "
                    "to Production Start."
                )

    @api.constrains("split_qty")
    def _check_split_qty(self):
        for wizard in self:
            if wizard.split_qty <= 0:
                raise ValidationError(
                    "Quantity yang akan di-split harus lebih dari 0."
                )

            if wizard.split_qty > wizard.remaining_qty:
                raise ValidationError(
                    "Quantity yang akan di-split tidak boleh "
                    "lebih besar dari remaining quantity."
                )

    def action_split(self):
        self.ensure_one()
        product_line = self.product_line_id

        # VALIDATION
        if product_line.parent_product_line_id:
            raise ValidationError(
                "Production Product hasil split tidak dapat "
                "di-split lagi."
            )

        if self.split_qty <= 0:
            raise ValidationError(
                "Quantity yang akan di-split harus lebih dari 0."
            )

        if self.split_qty > product_line.remaining_qty:
            raise ValidationError(
                "Quantity yang akan di-split melebihi "
                "remaining quantity."
            )

        # ------------------------------------------------------------
        # Pastikan partial tidak overlap ke belakang dengan window
        # main production yang sudah berjalan / split sebelumnya
        # ------------------------------------------------------------
        current_main_start = (
                product_line.production_start
                or product_line.plan_id.planned_start
        )

        if current_main_start and self.production_start < current_main_start:
            raise ValidationError(
                "Production Start partial tidak boleh lebih awal dari "
                f"jadwal Production saat ini ({current_main_start})."
            )

        new_main_start = self.production_end + timedelta(days=1)

        main_end = (
                product_line.production_end
                or product_line.plan_id.planned_end
        )

        if main_end and new_main_start > main_end:
            raise ValidationError(
                "Sisa waktu Production tidak cukup setelah Partial Production "
                "berakhir. Perpanjang Production End plan atau perkecil "
                "jadwal partial."
            )

        # GENERATE PRODUCTION NUMBER
        plan = product_line.plan_id

        base_number = (
                plan.production_po_number
                or plan.name
        )

        child_count = len(
            product_line.child_product_line_ids
        )

        suffix = chr(ord("A") + child_count)
        child_number = f"{base_number}{suffix}"

        # CREATE CHILD PRODUCT LINE
        child_line = self.env[
            "mrp.production.plan.product.line"
        ].create({
            "plan_id": product_line.plan_id.id,
            "product_id": product_line.product_id.id,
            "product_qty": self.split_qty,
            "parent_product_line_id": product_line.id,
            "production_number": child_number,
            "sequence": product_line.sequence + child_count + 1,
            "production_start": self.production_start,
            "production_end": self.production_end,
        })

        # COPY OPERATIONS FROM PARENT
        for operation_line in product_line.operation_line_ids:
            self.env[
                "mrp.production.plan.line"
            ].create({
                "product_line_id": child_line.id,
                "operation_id": operation_line.operation_id.id,
                "sequence": operation_line.sequence,
                "machine_id": operation_line.machine_id.id,
                "capacity_id": operation_line.capacity_id.id,
            })

        product_line.write({
            "production_start": new_main_start,
        })

        product_line.plan_id.message_post(
            body=(
                "<p><b>Production berhasil di-split.</b></p>"
                f"<p>"
                f"<b>Product:</b> "
                f"{product_line.product_id.display_name}"
                f"<br/>"
                f"<b>Production:</b> "
                f"{child_line.production_number}"
                f"<br/>"
                f"<b>Quantity:</b> "
                f"{self.split_qty}"
                f"</p>"
            )
        )

        return {
            "type": "ir.actions.act_window",
            "name": "Production Plan",
            "res_model": "mrp.production.plan",
            "view_mode": "form",
            "res_id": product_line.plan_id.id,
            "target": "current",
        }

        # return {
        #     "type": "ir.actions.act_window",
        #     "res_model": "mrp.production.plan.product.line",
        #     "res_id": child_line.id,
        #     "view_mode": "form",
        #     "target": "current",
        # }