from odoo import Command, api, fields, models
from odoo.exceptions import ValidationError
from datetime import timedelta, datetime
import math
import logging

_logger = logging.getLogger(__name__)

class ProductionPlan(models.Model):
    _name = "mrp.production.plan"
    _description = "Production Planning"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "planned_start desc"

    name = fields.Char(
        string="No. Plan",
        default="New",
        copy=False,
        tracking=True,
        help="Diketik manual. Kosongkan untuk nomor otomatis.",
    )

    sale_order_id = fields.Many2one(
        "sale.order",
        required=True,
        tracking=True,
    )

    origin_type = fields.Selection(
        [
            ("lokal", "Lokal"),
            ("import", "Import"),
        ],
        string="Tipe Produksi",
        default="lokal",
        required=True,
        tracking=True,
        help="Lokal: produk baru dibuat dari bahan baku. "
             "Import: produk yang sudah ada, hanya dikemas ulang dengan label brand client.",
    )

    customer_id = fields.Many2one(
        related="sale_order_id.partner_id",
        store=True,
    )

    mou_id = fields.Many2one(
        related="sale_order_id.mou_id",
        string="No. MOU",
        store=True,
    )

    brand_name = fields.Char(
        related="sale_order_id.brand_name",
        string="Nama Brand",
        store=True,
    )

    planned_start = fields.Date(
        required=False,
        tracking=True,
    )

    planned_end = fields.Date(
        required=False,
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

    stage_ids = fields.One2many(
        "mrp.production.plan.stage",
        "plan_id",
        string="Jadwal Proses",
    )

    manufacturing_order_ids = fields.One2many(
        "mrp.production",
        "production_plan_id",
        string="Perintah Produksi"
    )

    # Produk ada di baris (product_line_ids); field ini hanya terisi untuk plan turunan (split).
    product_id = fields.Many2one(
        "product.product",
        string="Product",
    )

    product_qty = fields.Float(
        string="Quantity",
    )

    product_uom_id = fields.Many2one(
        "uom.uom",
        related="product_id.uom_id",
        store=True,
    )

    product_line_ids = fields.One2many(
        "mrp.production.plan.product.line",
        "plan_id",
        string="Products",
    )

    manufacturing_order_ids = fields.One2many(
        "mrp.production",
        "production_plan_id",
        string="Perintah Produksi",
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

    purchase_order_ids = fields.Many2many(
        "purchase.order",
        "mrp_production_plan_purchase_order_rel",
        "plan_id",
        "purchase_order_id",
        string="PO Pembelian",
        domain="[('sale_order_id', '=', sale_order_id), ('state', '!=', 'cancel')]",
        help="PO yang dipakai plan ini. Satu SO bisa punya banyak PO; pilih yang untuk periode plan ini.",
    )

    production_po_number = fields.Char(
        string="No. PO Produksi",
        compute="_compute_production_po_number",
        help="Nomor PO yang dipilih di plan ini.",
    )

    production_number = fields.Char(
        string="No. Produksi",
        readonly=True,
        copy=False,
    )

    parent_plan_id = fields.Many2one(
        'mrp.production.plan',
        string='Production Plan Induk',
        readonly=True,
        copy=False,
    )

    child_plan_ids = fields.One2many(
        'mrp.production.plan',
        'parent_plan_id',
        string='Production Plan Anak',
    )

    is_child_plan = fields.Boolean(
        compute='_compute_is_child_plan',
        store=True,
    )

    has_child_production = fields.Boolean(
        string='Has Child Production',
        compute='_compute_has_child_production',
        store=True,
    )

    child_allocated_qty = fields.Float(
        string='Allocated Child Quantity',
        compute='_compute_child_quantities',
        store=True,
    )

    remaining_qty = fields.Float(
        string='Remaining Quantity',
        compute='_compute_child_quantities',
        store=True,
    )

    production_type = fields.Selection(
        [
            ('main', 'Main Production'),
            ('split', 'Production Split'),
            ('partial', 'Partial Production'),
        ],
        compute='_compute_production_type',
        store=True,
    )

    has_pending_mo = fields.Boolean(
        string="Belum Dibuat Perintah Produksi",
        compute="_compute_has_pending_mo",
    )

    @api.depends(
        "product_line_ids",
        "product_line_ids.manufacturing_order_ids",
        "product_line_ids.child_product_line_ids",
        "product_line_ids.child_product_line_ids.manufacturing_order_ids",
    )
    def _compute_has_pending_mo(self):
        for plan in self:
            effective_lines = plan._get_effective_product_lines()

            plan.has_pending_mo = any(
                not line.manufacturing_order_ids
                for line in effective_lines
            )

    @api.depends('parent_plan_id', 'child_plan_ids')
    def _compute_production_type(self):
        for plan in self:
            if plan.parent_plan_id:
                plan.production_type = 'partial'
            elif plan.child_plan_ids:
                plan.production_type = 'split'
            else:
                plan.production_type = 'main'

    @api.depends(
        'product_qty',
        'child_plan_ids.product_qty',
    )
    def _compute_child_quantities(self):
        for plan in self:
            allocated = sum(
                plan.child_plan_ids.mapped('product_qty')
            )

            plan.child_allocated_qty = allocated
            plan.remaining_qty = max(
                plan.product_qty - allocated,
                0,
            )

    @api.depends('parent_plan_id')
    def _compute_is_child_plan(self):
        for plan in self:
            plan.is_child_plan = bool(plan.parent_plan_id)

    @api.depends('child_plan_ids')
    def _compute_has_child_production(self):
        for plan in self:
            plan.has_child_production = bool(plan.child_plan_ids)

    @api.depends("purchase_order_ids")
    def _compute_production_po_number(self):
        for plan in self:
            plan.production_po_number = ", ".join(plan.purchase_order_ids.mapped("name")) or False

    def _finished_product_vals(self, product):
        self.ensure_one()
        line = self.env["mrp.production.plan.product.line"].new({"plan_id": self.id, "product_id": product.id})
        line.plan_id = self
        suggestion = line._suggest_finished_product()
        return {"finished_product_id": suggestion.id} if suggestion else {}

    def _set_product_lines(self, quantities):
        """Ganti baris produk dengan {product: qty}; qty tetap bisa diubah di form."""
        self.ensure_one()
        if not quantities or self._origin.product_line_ids.manufacturing_order_ids:
            return
        self.product_line_ids = [Command.clear()] + [
            Command.create({"product_id": product.id, "product_qty": qty, **self._finished_product_vals(product)})
            for product, qty in quantities.items()
        ]

    def _quantities_from_sale_order(self):
        self.ensure_one()
        quantities = {}
        for line in self.sale_order_id.order_line:
            if not line.display_type and line.product_id and line.product_id.type != "service":
                quantities[line.product_id] = quantities.get(line.product_id, 0) + line.product_uom_qty
        return quantities

    def _quantities_from_purchase_orders(self):
        """Qty produk SO yang tercantum di PO terpilih (PO bahan/kemasan biasanya tidak memuatnya)."""
        self.ensure_one()
        sale_products = self.sale_order_id.order_line.product_id
        quantities = {}
        for line in self.purchase_order_ids.order_line:
            if not line.display_type and line.product_id in sale_products:
                quantities[line.product_id] = quantities.get(line.product_id, 0) + line.product_qty
        return quantities

    @api.onchange("sale_order_id")
    def _onchange_sale_order_id(self):
        """PO dipilih otomatis bila SO hanya punya satu; produk diisi dari SO (atau PO bila memuatnya)."""
        for plan in self:
            if not plan.sale_order_id:
                plan.purchase_order_ids = False
                continue
            orders = self.env["purchase.order"].search([
                ("sale_order_id", "=", plan.sale_order_id.id),
                ("state", "!=", "cancel"),
            ])
            plan.purchase_order_ids = orders if len(orders) == 1 else False
            plan._set_product_lines(
                plan._quantities_from_purchase_orders() or plan._quantities_from_sale_order()
            )

    @api.onchange("purchase_order_ids")
    def _onchange_purchase_order_ids(self):
        """Bila PO memuat produk SO, qty-nya dipakai; selain itu daftar produk dibiarkan."""
        for plan in self:
            plan._set_product_lines(plan._quantities_from_purchase_orders())

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == "New":
                vals["name"] = (
                        self.env["ir.sequence"].next_by_code(
                            "mrp.production.plan"
                        )
                        or "New"
                )
        return super().create(vals_list)

    def onchange(self, values, field_names, fields_spec):
        """Nomor diketik manual: form baru dibuka dengan nomor kosong."""
        result = super().onchange(values, field_names, fields_spec)
        if not self and not field_names and "name" in fields_spec and not self.env.context.get("default_name"):
            result.setdefault("value", {})["name"] = False
        return result

    @api.constrains("name")
    def _check_unique_number(self):
        for plan in self:
            if plan.name and plan.name != "New" and self.search_count([
                ("id", "!=", plan.id),
                ("name", "=", plan.name),
            ]):
                raise ValidationError(f"Nomor {plan.name} sudah dipakai.")

    def action_generate_stages(self):
        """Susun Jadwal Proses dari tahap yang berlaku untuk Tipe Produksi plan ini."""
        Stage = self.env["mrp.production.stage"]
        for plan in self:
            if plan.state != "draft":
                raise ValidationError("Jadwal Proses hanya bisa disusun saat plan masih Draft.")
            if plan.material_check_state != "available":
                raise ValidationError(
                    "Cek ketersediaan material dulu. Jadwal Proses baru bisa "
                    "disusun setelah bahan cukup."
                )
            product_lines = plan._get_effective_product_lines()
            if not product_lines:
                raise ValidationError("Tambahkan produk dulu sebelum menyusun Jadwal Proses.")
            stages = Stage.search([("origin_type", "in", ("both", plan.origin_type))])
            # Tiap produk punya rangkaian tahapnya sendiri, supaya qty bagus dan QC tidak tercampur.
            plan.stage_ids = [Command.clear()] + [
                Command.create({
                    "product_line_id": product_line.id,
                    "stage_id": stage.id,
                    "sequence": stage.sequence,
                    "date_start": plan.planned_start,
                    "date_end": plan.planned_start,
                })
                for product_line in product_lines
                for stage in stages
            ]
            plan.state = "planned"
        return True

    def _finish_product_line(self, product_line, qty):
        """Packing selesai: selesaikan MO produk itu dengan qty bagus dari tahap terakhir."""
        self.ensure_one()
        open_orders = product_line.manufacturing_order_ids.filtered(lambda mo: mo.state not in ("done", "cancel"))
        batch_stage = self.stage_ids.filtered(
            lambda stage: stage.product_line_id == product_line and stage.set_batch and stage.batch_no
        )[:1]
        if open_orders:
            order = open_orders[0]
            order.qty_producing = qty
            if batch_stage and order.product_tracking == "lot":
                order.lot_producing_ids = self.env["stock.lot"].create({
                    "name": batch_stage.batch_no,
                    "product_id": order.product_id.id,
                    "company_id": order.company_id.id,
                    "expiration_date": datetime.combine(batch_stage.expiry_date, datetime.min.time()),
                })
            order.with_context(
                skip_backorder=True, skip_consumption=True, skip_immediate=True,
            ).button_mark_done()
            self.message_post(
                body=f"{product_line.product_id.display_name}: Packing selesai, {qty:g} masuk stok (Perintah Produksi {order.name})."
                     + (f" Batch {batch_stage.batch_no}, expired {batch_stage.expiry_date}." if batch_stage else ""),
                subtype_xmlid="mail.mt_note",
            )
        if all(
            stage.state == "done" for stage in self.stage_ids
        ) and all(
            line.manufacturing_order_ids and all(mo.state in ("done", "cancel") for mo in line.manufacturing_order_ids)
            for line in self._get_effective_product_lines()
        ):
            self.state = "done"

    def _produced_quantities(self):
        """(qty jadi, qty rencana): hasil bagus tahap terakhir tiap produk."""
        self.ensure_one()
        produced = 0.0
        for product_line in self._get_effective_product_lines():
            stages = self.stage_ids.filtered(lambda stage: stage.product_line_id == product_line)
            last = stages.sorted(key=lambda stage: (stage.sequence, stage.id))[-1:]
            if last and last.state == "done":
                produced += last.qty_good
        planned = sum(self._get_effective_product_lines().mapped("production_qty"))
        return produced, planned

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
        Schedule = self.env["mrp.production.machine.schedule"]

        def _to_date(value):
            """Normalize Date / Datetime values into a Python date."""
            if not value:
                return False

            if isinstance(value, datetime):
                return value.date()

            return value

        for plan in self:
            # ============================================================
            # 1. VALIDATE PLANNING PERIOD
            if not plan.planned_start:
                raise ValidationError(
                    "Please set Planning Start date."
                )

            if not plan.planned_end:
                raise ValidationError(
                    "Please set Planning End date."
                )

            plan_start = _to_date(plan.planned_start)
            plan_end = _to_date(plan.planned_end)

            if plan_end < plan_start:
                raise ValidationError(
                    "Planning End cannot be earlier than Planning Start."
                )

            # ============================================================
            # 2. VALIDATE PRODUCT LINES
            if not plan.product_line_ids:
                raise ValidationError(
                    "Please add at least one product."
                )

            effective_lines = plan._get_effective_product_lines()

            if not effective_lines:
                raise ValidationError(
                    "No effective production products found."
                )

            pending_lines = effective_lines.filtered(
                lambda pl: not pl.manufacturing_order_ids
            )

            if not pending_lines:
                raise ValidationError(
                    "Semua production batch sudah memiliki Perintah Produksi. "
                    "Tidak ada yang perlu di-check ulang."
                )

            for product_line in effective_lines:

                if not product_line.product_id:
                    raise ValidationError(
                        "Please select product for all product lines."
                    )

                if (
                    not product_line.production_qty
                    or product_line.production_qty <= 0
                ):
                    raise ValidationError(
                        f"Invalid production quantity for "
                        f"{product_line.product_id.display_name}."
                    )

                if not product_line.operation_line_ids:
                    raise ValidationError(
                        f"Please load BOM operations first for "
                        f"{product_line.product_id.display_name}."
                    )

                # --------------------------------------------------------
                # Normalize Product Line production dates
                # --------------------------------------------------------

                production_start = (
                        _to_date(product_line.production_start)
                        or plan_start
                )

                production_end = (
                        _to_date(product_line.production_end)
                        or plan_end
                )

                # --------------------------------------------------------
                # Validate Product Line production period
                # --------------------------------------------------------

                if production_end < production_start:
                    raise ValidationError(
                        f"Production End cannot be earlier than "
                        f"Production Start for "
                        f"{product_line.product_id.display_name}."
                    )

                # Production must stay inside Planning Period
                if production_start < plan_start:
                    raise ValidationError(
                        f"Production Start for "
                        f"{product_line.product_id.display_name} "
                        f"cannot be earlier than Planning Start "
                        f"({plan_start})."
                    )

                if production_end > plan_end:
                    raise ValidationError(
                        f"Production End for "
                        f"{product_line.product_id.display_name} "
                        f"cannot be later than Planning End "
                        f"({plan_end})."
                    )

            # ============================================================
            # 3. DELETE OLD MACHINE SCHEDULE
            #    belum punya MO. Schedule baris yang sudah committed
            #    dibiarkan utuh supaya kapasitas mesin yang sudah terpakai
            #    tetap kehitung saat baris pending lain di-generate.
            pending_operation_lines = pending_lines.mapped("operation_line_ids")

            Schedule.search([
                ("plan_line_id", "in", pending_operation_lines.ids),
            ]).unlink()

            pending_operation_lines.write({
                "planned_start": False,
                "planned_end": False,
            })

            # ============================================================
            # 4. GENERATE MACHINE SCHEDULE
            latest_schedule_end = plan_start

            scheduling_lines = pending_lines.sorted(
                key=lambda pl: (
                    _to_date(pl.production_start) or plan_start,
                    pl.sequence,
                )
            )

            for product_line in scheduling_lines:
                production_start = (
                        _to_date(product_line.production_start)
                        or plan_start
                )

                production_end = (
                        _to_date(product_line.production_end)
                        or plan_end
                )

                # First operation starts from Product Line
                # Production Start
                current_start = production_start

                lines = product_line.operation_line_ids.sorted(
                    key=lambda line: line.sequence
                )

                for line in lines:

                    # ----------------------------------------------------
                    # Validate Machine
                    # ----------------------------------------------------

                    if not line.machine_id:
                        raise ValidationError(
                            f"Please select machine for operation "
                            f"'{line.operation_id.display_name}' "
                            f"of product "
                            f"'{product_line.product_id.display_name}'."
                        )

                    # ----------------------------------------------------
                    # Validate Machine / Work Center
                    # ----------------------------------------------------

                    if (
                            line.machine_id.workcenter_id
                            != line.operation_id.workcenter_id
                    ):
                        raise ValidationError(
                            f"Machine "
                            f"'{line.machine_id.display_name}' "
                            f"does not belong to the work center "
                            f"'{line.operation_id.workcenter_id.display_name}' "
                            f"for operation "
                            f"'{line.operation_id.display_name}'."
                        )

                    # ----------------------------------------------------
                    # Validate Capacity
                    # ----------------------------------------------------

                    if not line.capacity_id:
                        raise ValidationError(
                            f"Please select machine capacity for "
                            f"operation "
                            f"'{line.operation_id.display_name}' "
                            f"of product "
                            f"'{product_line.product_id.display_name}'."
                        )

                    capacity = line.capacity_id.capacity_per_day

                    if capacity <= 0:
                        raise ValidationError(
                            f"Capacity per day must be greater than zero "
                            f"for operation "
                            f"'{line.operation_id.display_name}' "
                            f"of product "
                            f"'{product_line.product_id.display_name}'."
                        )

                    # ----------------------------------------------------
                    # Prepare quantity
                    # ----------------------------------------------------

                    remaining_qty = product_line.production_qty

                    schedule_date = current_start
                    sequence = 1

                    operation_start = False
                    operation_end = False

                    # ====================================================
                    # 5. SPLIT QUANTITY INTO DAILY MACHINE SCHEDULE
                    while remaining_qty > 0:

                        # ------------------------------------------------
                        # Cannot exceed Product Line Production End
                        # ------------------------------------------------

                        if schedule_date > production_end:
                            raise ValidationError(
                                f"Production for product "
                                f"'{product_line.product_id.display_name}' "
                                f"and operation "
                                f"'{line.operation_id.display_name}' "
                                f"cannot be completed within the "
                                f"production period "
                                f"{production_start} - {production_end}."
                            )

                        # ------------------------------------------------
                        # Get available machine capacity
                        # ------------------------------------------------

                        available_capacity = self._get_available_capacity(
                            line.machine_id,
                            capacity,
                            schedule_date,
                        )

                        # ------------------------------------------------
                        # If machine is full, move to next day
                        # ------------------------------------------------

                        if available_capacity <= 0:
                            schedule_date += timedelta(days=1)
                            continue

                        # ------------------------------------------------
                        # Determine daily production quantity
                        # ------------------------------------------------

                        daily_qty = min(
                            available_capacity,
                            remaining_qty,
                        )

                        # ------------------------------------------------
                        # Create Machine Schedule
                        # ------------------------------------------------

                        Schedule.create({
                            "plan_id": plan.id,
                            "plan_line_id": line.id,
                            "operation_id": line.operation_id.id,
                            "machine_id": line.machine_id.id,
                            "capacity_id": line.capacity_id.id,
                            "product_id": product_line.product_id.id,
                            "planned_qty": daily_qty,
                            "daily_qty": daily_qty,
                            "schedule_sequence": sequence,
                            "planned_start": schedule_date,
                            "planned_end": schedule_date,
                        })

                        # ------------------------------------------------
                        # Track operation start/end
                        # ------------------------------------------------

                        if not operation_start:
                            operation_start = schedule_date

                        operation_end = schedule_date

                        # ------------------------------------------------
                        # Reduce remaining quantity
                        # ------------------------------------------------

                        remaining_qty -= daily_qty

                        sequence += 1

                        # ------------------------------------------------
                        # If quantity still remains,
                        # continue on next day
                        # ------------------------------------------------

                        if remaining_qty > 0:
                            schedule_date += timedelta(days=1)

                    # ====================================================
                    # 6. SAVE GENERATED OPERATION PERIOD
                    if operation_start and operation_end:
                        # Next operation starts after this operation
                        current_start = operation_end

                        if operation_end > latest_schedule_end:
                            latest_schedule_end = operation_end

            # ============================================================
            # 7. FINAL VALIDATION
            if latest_schedule_end > plan_end:
                raise ValidationError(
                    "Generated machine schedule exceeds "
                    "the Planning End date."
                )

            # ============================================================
            # 8. UPDATE PLAN STATUS
            plan.capacity_checked = True

            if plan.state == "draft":
                plan.state = "planned"

        return True

    def action_create_mo(self):
        _logger.warning(
            "========== ACTION CREATE MO DIPANGGIL =========="
        )

        Production = self.env["mrp.production"]

        for plan in self:
            stage_mode = bool(plan.stage_ids)

            if not stage_mode and not plan.capacity_checked:
                raise ValidationError(
                    "Please check production capacity first."
                )

            if not stage_mode and not plan.machine_schedule_ids:
                raise ValidationError(
                    "No machine schedule found."
                )

            if not plan.product_line_ids:
                raise ValidationError(
                    "Production Plan has no products."
                )

            effective_lines = plan._get_effective_product_lines()

            if not effective_lines:
                raise ValidationError(
                    "No production products found."
                )

            pending_lines = effective_lines.filtered(
                lambda line: not line.manufacturing_order_ids
            )

            if not pending_lines:
                raise ValidationError(
                    "All production batches already have "
                    "Perintah Produksi."
                )

            selected_lines = pending_lines.filtered(
                lambda line: line.create_mo
            )

            if not selected_lines:
                raise ValidationError(
                    "Please select at least one production batch "
                    "to create a Perintah Produksi."
                )

            created_mos = self.env["mrp.production"]

            for product_line in selected_lines:
                production_qty = product_line.production_qty

                if not production_qty or production_qty <= 0:
                    raise ValidationError(
                        f"Invalid production quantity for "
                        f"{product_line.product_id.display_name}."
                    )

                bom = self.env["mrp.bom"].search([
                    (
                        "product_tmpl_id",
                        "=",
                        product_line.bom_product_id.product_tmpl_id.id,
                    )
                ], limit=1)

                if not bom:
                    raise ValidationError(
                        f"No Bill of Materials found for "
                        f"{product_line.bom_product_id.display_name}."
                    )

                mo = Production.create({
                    "product_id": product_line.bom_product_id.id,
                    "product_qty": production_qty,
                    "product_uom_id": product_line.bom_product_id.uom_id.id,
                    "bom_id": bom.id,
                    "production_plan_id": plan.id,
                    "production_plan_product_line_id": product_line.id,
                })

                mo.action_confirm()

                if not stage_mode and not mo.workorder_ids:
                    raise ValidationError(
                        f"Perintah Produksi for "
                        f"{product_line.product_id.display_name} "
                        f"was created, but no Work Orders were generated."
                    )

                created_mos |= mo

                schedules = self.env[
                    "mrp.production.machine.schedule"
                ].search([
                    (
                        "plan_line_id",
                        "in",
                        product_line.operation_line_ids.ids,
                    )
                ])

                # ----------------------------------------------------
                # Pecah Work Order jadi 1 per baris schedule (per hari),
                # bukan 1 Work Order untuk seluruh rentang tanggal
                # operation. Supaya kalau operation ini "dicicil" ke
                # beberapa hari yang tidak berurutan (diselang-seling
                # production lain), tiap potongan hari punya Work
                # Order sendiri dengan tanggal & qty yang benar.
                # ----------------------------------------------------

                operations = schedules.mapped("operation_id")

                for operation in operations:
                    op_schedules = schedules.filtered(
                        lambda s: s.operation_id == operation
                    ).sorted(key=lambda s: s.planned_start)

                    base_workorder = mo.workorder_ids.filtered(
                        lambda wo: wo.operation_id == operation
                    )[:1]

                    if not base_workorder:
                        _logger.warning(
                            "Tidak ada Work Order Odoo untuk operation %s "
                            "pada MO %s - dilewati.",
                            operation.display_name,
                            mo.name,
                        )
                        continue

                    original_duration = base_workorder.duration_expected
                    original_state = base_workorder.state

                    total_qty = sum(
                        op_schedules.mapped("planned_qty")
                    ) or 1.0

                    for index, schedule in enumerate(op_schedules):

                        if index == 0:
                            # Baris pertama pakai Work Order bawaan yang
                            # sudah dibuat action_confirm()
                            workorder = base_workorder
                        else:
                            # Baris selanjutnya = duplikat Work Order
                            # untuk potongan hari berikutnya
                            workorder = base_workorder.copy({
                                "qty_producing": 0,
                                "qty_produced": 0,
                            })
                            workorder.state = original_state

                        ratio = schedule.planned_qty / total_qty

                        workorder.write({
                            "date_start": fields.Datetime.to_datetime(
                                schedule.planned_start
                            ),
                            "date_finished": fields.Datetime.to_datetime(
                                schedule.planned_end
                            ),
                            "qty_producing": schedule.planned_qty,
                            "duration_expected": (
                                    original_duration * ratio
                            ),
                        })

                        schedule.workorder_id = workorder.id

                        _logger.warning(
                            "CREATE MO - Schedule %s | Product=%s | "
                            "Operation=%s | WO=%s | Start=%s | End=%s | Qty=%s",
                            schedule.id,
                            schedule.product_id.display_name,
                            schedule.operation_id.name,
                            workorder.id,
                            schedule.planned_start,
                            schedule.planned_end,
                            schedule.planned_qty,
                        )

                product_line.create_mo = False

            if not created_mos:
                raise ValidationError(
                    "No Perintah Produksi was created."
                )

            plan.state = "running"

        return True

    def _get_production_bom(self, product_line):
        """BOM produk jadi. Lokal dibuat dari 0: BOM wajib gabungan
        beberapa bahan yang diolah jadi 1 produk."""
        self.ensure_one()
        product = product_line.bom_product_id
        bom = self.env["mrp.bom"].search([
            ("product_tmpl_id", "=", product.product_tmpl_id.id),
        ], limit=1)

        if not bom:
            if self.origin_type == "import":
                raise ValidationError(
                    f"Produk Import {product.display_name} belum punya BOM repack. "
                    f"Pilih Produk Jadi (brand) di baris produk, atau buat BOM berisi produk asal, "
                    f"label, dan kemasan agar stoknya bisa dicek."
                )
            raise ValidationError(
                f"BOM not found for "
                f"{product.display_name}."
            )

        if self.origin_type == "lokal":
            materials = bom.bom_line_ids.product_id - product
            if len(materials) < 2:
                raise ValidationError(
                    f"Produk Lokal {product.display_name} dibuat dari 0, jadi BOM-nya harus "
                    f"berisi minimal 2 bahan berbeda yang digabung jadi 1 produk. "
                    f"BOM {bom.display_name} baru berisi {len(materials)} bahan."
                )

        return bom

    def action_load_operations(self):
        OperationLine = self.env["mrp.production.plan.line"]

        for plan in self:
            if not plan.product_line_ids:
                raise ValidationError("Please add at least one product.")

            for product_line in plan.product_line_ids:
                if not product_line.product_id:
                    raise ValidationError("Please select product first.")

                # Baris yang MO-nya sudah dibuat tidak boleh di-reload
                # operasinya — itu akan cascade-delete schedule yang
                # sudah terhubung ke Work Order yang berjalan.
                if product_line.manufacturing_order_ids:
                    continue

                bom = plan._get_production_bom(product_line)

                product_line.operation_line_ids.unlink()

                vals = []
                for index, operation in enumerate(bom.operation_ids, start=1):
                    vals.append({
                        "product_line_id": product_line.id,
                        "operation_id": operation.id,
                        "sequence": index * 10,
                    })

                if vals:
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
        "stage_ids.state",
    )
    def _compute_progress(self):
        for plan in self:
            if plan.stage_ids:
                plan.progress = len(plan.stage_ids.filtered(lambda stage: stage.state == "done")) \
                    / len(plan.stage_ids) * 100
                continue
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

        def _to_date(value):
            if not value:
                return False
            if isinstance(value, datetime):
                return value.date()
            return value

        for plan in self:
            effective_lines = plan._get_effective_product_lines()

            if not effective_lines:
                raise ValidationError(
                    "No production products found."
                )

            for product_line in effective_lines:

                # Tanggal cek harus tanggal mulai produksi BARIS INI,
                # bukan selalu tanggal awal plan — beda product line
                # bisa punya production_start yang berbeda-beda.
                check_date = (
                        _to_date(product_line.production_start)
                        or _to_date(plan.planned_start)
                )

                for line in product_line.operation_line_ids:

                    if not line.machine_id:
                        raise ValidationError(
                            f"Machine not assigned for "
                            f"{line.operation_id.name} "
                            f"({product_line.product_id.display_name})"
                        )

                    if not line.capacity_id:
                        raise ValidationError(
                            f"Capacity not assigned for "
                            f"{line.operation_id.name} "
                            f"({product_line.product_id.display_name})"
                        )

                    capacity = (
                        line.capacity_id.capacity_per_day
                    )

                    if capacity <= 0:
                        raise ValidationError(
                            f"Invalid capacity for "
                            f"{line.machine_id.name}."
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
                                check_date
                            ),
                            (
                                "state",
                                "!=",
                                "done"
                            ),
                        ]).mapped("planned_qty")
                    )

                    if qty_used >= capacity:
                        raise ValidationError(
                            f"Machine {line.machine_id.name} "
                            f"is already full on {check_date} for "
                            f"{product_line.product_id.display_name}."
                        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Available",
                "message": "All machines are available.",
                "type": "success",
            }
        }

    def action_reset_planning(self):
        for plan in self:
            if plan.manufacturing_order_ids:
                raise ValidationError(
                    "Production Plan ini sudah memiliki Manufacturing "
                    "Order. Reset tidak diperbolehkan karena akan "
                    "menghapus data yang sudah committed."
                )

            plan.machine_schedule_ids.unlink()
            plan.stage_ids.unlink()
            plan.material_shortage_ids.unlink()

            plan.capacity_checked = False
            plan.material_checked = False
            plan.material_check_state = "not_checked"

            plan.state = "draft"

        return True

    def action_validate_planning(self):
        for plan in self:
            errors = []

            # ==========================================================
            # BASIC VALIDATION
            # ==========================================================

            if not plan.product_line_ids:
                errors.append(
                    "• No production products added."
                )

            stage_mode = bool(plan.stage_ids)

            if stage_mode:
                for stage in plan.stage_ids:
                    if not stage.date_start or not stage.date_end:
                        errors.append(
                            f"• Tahap {stage.stage_id.name}: tanggal mulai/selesai belum diisi."
                        )
                dates = plan.stage_ids.mapped("date_start") + plan.stage_ids.mapped("date_end")
                dates = [date for date in dates if date]
                if dates and not plan.planned_start:
                    plan.planned_start = min(dates)
                if dates and not plan.planned_end:
                    plan.planned_end = max(dates)

            if not plan.planned_start:
                errors.append(
                    "• Planning start date is empty."
                )

            # ==========================================================
            # PRODUCT LINE VALIDATION
            # ==========================================================

            for product_line in plan._get_effective_product_lines():
                product_name = (
                    product_line.product_id.display_name
                    if product_line.product_id
                    else f"Line {product_line.sequence}"
                )

                # PRODUCT
                if not product_line.product_id:
                    errors.append(
                        f"• {product_name}: Product is empty."
                    )
                    continue

                # QUANTITY
                if (
                        not product_line.product_qty
                        or product_line.product_qty <= 0
                ):
                    errors.append(
                        f"• {product_name}: "
                        "Production quantity must be greater than zero."
                    )

                # OPERATIONS
                if not stage_mode and not product_line.operation_line_ids:
                    errors.append(
                        f"• {product_name}: "
                        "No BOM operations loaded."
                    )

                # BOM
                bom = self.env["mrp.bom"].search([
                    (
                        "product_tmpl_id",
                        "=",
                        product_line.bom_product_id.product_tmpl_id.id,
                    )
                ], limit=1)

                if not bom:
                    errors.append(
                        f"• {product_name}: BOM not found."
                    )

            # ==========================================================
            # CAPACITY VALIDATION
            # ==========================================================

            if not stage_mode and not plan.capacity_checked:
                errors.append(
                    "• Machine capacity has not been checked."
                )

            if not stage_mode and not plan.machine_schedule_ids:
                errors.append(
                    "• Machine capacity planning has not been generated."
                )

            # ==========================================================
            # MATERIAL VALIDATION
            # ==========================================================

            if not plan.material_checked:
                errors.append(
                    "• Material availability has not been checked."
                )

            elif plan.material_check_state == "shortage":
                errors.append(
                    "• Material shortage found. "
                    "Please resolve material shortage before approval."
                )

            # ==========================================================
            # PROCESS VALIDATION
            # ==========================================================

            for product_line in plan._get_effective_product_lines():
                product_name = (
                    product_line.product_id.display_name
                    if product_line.product_id
                    else f"Line {product_line.sequence}"
                )

                for line in (product_line.operation_line_ids if not stage_mode else []):

                    operation_name = (
                            line.operation_id.name
                            or "Unknown Operation"
                    )

                    if not line.machine_id:
                        errors.append(
                            f"• {product_name} - {operation_name}: "
                            "Machine not assigned."
                        )

                    if not line.capacity_id:
                        errors.append(
                            f"• {product_name} - {operation_name}: "
                            "Capacity not assigned."
                        )

                    if line.capacity_per_day <= 0:
                        errors.append(
                            f"• {product_name} - {operation_name}: "
                            "Invalid capacity."
                        )

                    if not line.schedule_ids:
                        errors.append(
                            f"• {product_name} - {operation_name}: "
                            "Machine schedule not generated."
                        )

            # ==========================================================
            # FINAL VALIDATION
            # ==========================================================

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
        MaterialShortage = self.env[
            "mrp.production.material.shortage"
        ]

        for plan in self:

            # ==========================================================
            # RESET HASIL CHECK SEBELUMNYA
            # ==========================================================

            plan.material_shortage_ids.unlink()

            plan.material_checked = False
            plan.material_check_state = "not_checked"

            # ==========================================================
            # BASIC VALIDATION
            # ==========================================================

            if not plan.product_line_ids:
                raise ValidationError(
                    "Please add at least one product."
                )

            has_shortage = False
            material_lines = []

            # ==========================================================
            # LOOP PRODUCT LINE
            # ==========================================================

            for product_line in plan._get_effective_product_lines():
                if not product_line.product_id:
                    raise ValidationError(
                        "Please select product for all product lines."
                    )

                if (
                        not product_line.product_qty
                        or product_line.product_qty <= 0
                ):
                    raise ValidationError(
                        f"Please set a valid production quantity "
                        f"for {product_line.product_id.display_name}."
                    )

                # ======================================================
                # FIND BOM
                # ======================================================

                bom = plan._get_production_bom(product_line)

                # ======================================================
                # CHECK MATERIAL
                # ======================================================

                for bom_line in bom.bom_line_ids:

                    material = bom_line.product_id

                    required_qty = (
                            bom_line.product_qty
                            * product_line.product_qty
                            / bom.product_qty
                    )

                    available_qty = material.qty_available

                    shortage_qty = (
                            required_qty
                            - available_qty
                    )

                    if shortage_qty > 0:
                        has_shortage = True

                    material_lines.append({
                        "plan_id": plan.id,

                        # PRODUCT LINE
                        "product_line_id": (
                            product_line.id
                        ),

                        "product_id": material.id,
                        "required_qty": required_qty,
                        "available_qty": available_qty,
                        "shortage_qty": max(
                            shortage_qty,
                            0,
                        ),
                    })

            # ==========================================================
            # SAVE MATERIAL RESULT
            # ==========================================================

            if material_lines:
                MaterialShortage.create(
                    material_lines
                )

            # ==========================================================
            # UPDATE STATUS
            # ==========================================================

            plan.material_checked = True

            if has_shortage:
                plan.material_check_state = "shortage"
            else:
                plan.material_check_state = "available"

        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }

    def action_view_parent_production(self):
        self.ensure_one()

        if not self.parent_plan_id:
            return False

        return {
            'type': 'ir.actions.act_window',
            'name': 'Parent Production',
            'res_model': 'mrp.production.plan',
            'view_mode': 'form',
            'res_id': self.parent_plan_id.id,
            'target': 'current',
        }

    def _get_effective_product_lines(self):
        self.ensure_one()

        ProductLine = self.env["mrp.production.plan.product.line"]
        result = ProductLine

        for line in self.product_line_ids:
            if line.child_product_line_ids:
                result |= line.child_product_line_ids

                # Parent masih mewakili quantity yang belum di-split
                if line.remaining_qty > 0:
                    result |= line
            else:
                result |= line

        return result.sorted(key=lambda x: x.sequence)

class DashboardTimeline(models.Model):
    """
    Inherit model dashboard.timeline.mou mengisi hook _get_production_data() yang di custom_mou masih kosong.
    """
    _inherit = "dashboard.timeline.mou"

    def _get_production_data(self, mou_id):
        plans = self.env["mrp.production.plan"].search([
            ("sale_order_id.mou_id", "=", mou_id),
        ])

        # Total kesepakatan MOU (semua produk), pembanding hasil Packing seluruh plan.
        mou_qty_total = sum(self.env["draft.maklon"].browse(mou_id).maklon_line_ids.mapped("product_qty"))

        result = []
        for plan in plans:
            mo_ids = plan.manufacturing_order_ids
            mo_done = mo_ids.filtered(lambda m: m.state == "done")
            qty_done, qty_plan = plan._produced_quantities()

            result.append({
                "id": plan.id,
                "name": plan.name,
                "product": plan.product_id.display_name or ", ".join(
                    plan.product_line_ids.product_id.mapped("display_name")
                ),
                "origin_label": dict(plan._fields["origin_type"].selection).get(plan.origin_type, ""),
                "state": plan.state,
                "state_label": dict(
                    plan._fields["state"].selection
                ).get(plan.state, plan.state),
                "progress": round(plan.progress or 0.0, 1),
                "is_done": plan.state == "done",
                "is_cancelled": plan.state == "cancel",
                "planned_start": (
                    fields.Date.to_string(plan.planned_start)
                    if plan.planned_start else None
                ),
                "planned_end": (
                    fields.Date.to_string(plan.planned_end)
                    if plan.planned_end else None
                ),
                "mou_qty_total": mou_qty_total,
                "qty_done": qty_done if plan.state != "cancel" else 0.0,
                "qty_plan": qty_plan,
                "mo_count": len(mo_ids),
                "mo_done": len(mo_done),
            })

        return result