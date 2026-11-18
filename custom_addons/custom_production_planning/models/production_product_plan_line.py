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

    finished_product_id = fields.Many2one(
        "product.product",
        string="Produk Jadi (brand)",
        help="Produk yang akan dihasilkan, supaya jelas jadi produk apa. Lokal: produk baru hasil "
             "produksi. Import: produk brand client hasil kemas ulang. BOM, Check Material, Perintah Produksi, "
             "dan stok memakai produk ini. Kosongkan bila produk di kolom Product sudah produk jadi.",
    )

    bom_product_id = fields.Many2one(
        "product.product",
        string="Produk yang Diproduksi",
        compute="_compute_bom_product_id",
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
        string="Perintah Produksi",
    )

    stage_ids = fields.One2many(
        "mrp.production.plan.stage",
        "product_line_id",
        string="Tahapan",
    )

    stage_start = fields.Date(string="Mulai Tahap", compute="_compute_stage_summary")
    stage_end = fields.Date(string="Selesai Tahap", compute="_compute_stage_summary")
    stage_progress = fields.Char(string="Tahap Berjalan", compute="_compute_stage_summary")

    @api.depends("stage_ids.state", "stage_ids.date_start", "stage_ids.date_end", "stage_ids.sequence")
    def _compute_stage_summary(self):
        labels = {"todo": "Belum Mulai", "in_progress": "Berjalan", "waiting_qc": "Menunggu QC", "done": "Selesai"}
        for line in self:
            stages = line.stage_ids.sorted(key=lambda s: (s.sequence, s.id))
            starts = [d for d in stages.mapped("date_start") if d]
            ends = [d for d in stages.mapped("date_end") if d]
            line.stage_start = min(starts) if starts else False
            line.stage_end = max(ends) if ends else False
            if not stages:
                line.stage_progress = False
                continue
            done = len(stages.filtered(lambda s: s.state == "done"))
            current = stages.filtered(lambda s: s.state != "done")[:1]
            line.stage_progress = (
                f"{done}/{len(stages)} selesai"
                + (f" · {current.stage_id.name} ({labels.get(current.state, current.state)})" if current else "")
            )

    material_ids = fields.One2many(
        "mrp.production.material.shortage", "product_line_id", string="Daftar Bahan",
    )
    material_summary = fields.Char(string="Bahan", compute="_compute_material_summary")

    @api.depends("material_ids.shortage_qty")
    def _compute_material_summary(self):
        for line in self:
            total = len(line.material_ids)
            short = len(line.material_ids.filtered(lambda m: m.shortage_qty > 0))
            if not total:
                line.material_summary = False
            elif short:
                line.material_summary = f"{short} dari {total} bahan kurang"
            else:
                line.material_summary = f"{total} bahan cukup"

    finished_uom_id = fields.Many2one(
        "uom.uom", string="Satuan Produk Jadi", compute="_compute_finished_uom_id",
    )

    @api.depends("finished_product_id.uom_id", "product_id.uom_id")
    def _compute_finished_uom_id(self):
        for line in self:
            line.finished_uom_id = (line.finished_product_id or line.product_id).uom_id
    finished_qty_available = fields.Float(
        string="Stok Produk Jadi", compute="_compute_finished_stock",
        help="Stok on hand produk jadi saat ini di gudang.",
    )
    finished_qty_forecast = fields.Float(
        string="Perkiraan Stok", compute="_compute_finished_stock",
        help="Stok on hand + yang akan masuk (Perintah Produksi / pembelian) - yang akan keluar (pengiriman).",
    )
    finished_stock_status = fields.Char(string="Status Stok", compute="_compute_finished_stock")

    @api.depends("bom_product_id", "production_qty")
    def _compute_finished_stock(self):
        for line in self:
            product = line.bom_product_id
            on_hand = product.qty_available if product else 0.0
            line.finished_qty_available = on_hand
            line.finished_qty_forecast = product.virtual_available if product else 0.0
            if not product:
                line.finished_stock_status = False
            elif on_hand <= 0:
                line.finished_stock_status = "Belum ada stok"
            elif on_hand >= line.production_qty:
                line.finished_stock_status = "Stok sudah cukup"
            else:
                line.finished_stock_status = f"Stok kurang {line.production_qty - on_hand:g}"

    def action_open_material_popup(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Bahan {self.bom_product_id.display_name}",
            "res_model": self._name,
            "res_id": self.id,
            "views": [(self.env.ref("custom_production_planning.view_production_plan_product_line_material_form").id, "form")],
            "target": "new",
        }

    def action_open_stage_popup(self):
        """Popup untuk mengatur tanggal, PIC, dan mesin tiap tahap produk ini."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Tahapan {self.bom_product_id.display_name}",
            "res_model": self._name,
            "res_id": self.id,
            "views": [(self.env.ref("custom_production_planning.view_production_plan_product_line_stage_form").id, "form")],
            "target": "new",
        }

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
        string="Buat Perintah Produksi",
        default=False,
        readonly=False,
    )

    has_mo = fields.Boolean(
        string="Sudah Ada Perintah Produksi",
        compute="_compute_has_mo",
        store=True,
    )

    @api.depends("product_id", "finished_product_id")
    def _compute_bom_product_id(self):
        for line in self:
            line.bom_product_id = line.finished_product_id or line.product_id

    def _suggest_finished_product(self):
        """Import: barang impor yang hanya dipakai di satu BOM produk brand diisi otomatis."""
        self.ensure_one()
        if self.plan_id.origin_type != "import" or not self.product_id:
            return self.env["product.product"]
        Bom = self.env["mrp.bom"]
        if Bom.search_count([("product_tmpl_id", "=", self.product_id.product_tmpl_id.id)]):
            return self.env["product.product"]  # sudah punya BOM sendiri
        brands = Bom.search([("bom_line_ids.product_id", "=", self.product_id.id)]).product_tmpl_id
        return brands.product_variant_id if len(brands) == 1 else self.env["product.product"]

    @api.onchange("product_id")
    def _onchange_product_id_suggest_finished(self):
        for line in self:
            line.finished_product_id = line._suggest_finished_product()

    def action_create_mo(self):
        """Tombol Buat MO di baris produk."""
        for line in self:
            if line.plan_id.state not in ("approved", "running"):
                raise ValidationError("Approve Planning dulu sebelum membuat Perintah Produksi.")
            if line.has_mo:
                raise ValidationError("Perintah Produksi untuk baris ini sudah dibuat.")
            line.plan_id.action_create_mo(only_lines=line)
        return True

    def action_open_mo(self):
        self.ensure_one()
        mo = self.manufacturing_order_ids[:1]
        if not mo:
            raise ValidationError("Perintah Produksi untuk produk ini belum dibuat.")
        return {
            "type": "ir.actions.act_window",
            "name": mo.name,
            "res_model": "mrp.production",
            "res_id": mo.id,
            "views": [(False, "form")],
        }

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
        "stage_ids.state",
        "manufacturing_order_ids",
        "manufacturing_order_ids.workorder_ids",
        "manufacturing_order_ids.workorder_ids.state",
    )
    def _compute_progress(self):
        for line in self:
            # Progress dari tahap proses (sama seperti progress Plan); Work Order hanya cadangan.
            if line.stage_ids:
                line.progress = len(line.stage_ids.filtered(lambda s: s.state == "done")) / len(line.stage_ids) * 100
                continue
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

    @api.model
    def _recompute_stage_progress(self):
        """Tiap Upgrade: progress produk yang sudah ada dihitung ulang dari tahap proses."""
        lines = self.search([("stage_ids", "!=", False)])
        self.env.add_to_compute(self._fields["progress"], lines)
        lines._recompute_recordset(["progress"])

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
                "Perintah Produksi sudah dibuat."
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