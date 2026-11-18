from odoo import api, fields, models
from odoo.exceptions import UserError

class MrpProduction(models.Model):
    _inherit = "mrp.production"

    # Status "To Close" ditampilkan sebagai "Progress": produksi masih berlangsung sampai ditutup.
    state = fields.Selection(selection_add=[("to_close", "Progress")])

    production_plan_id = fields.Many2one(
        "mrp.production.plan",
        string="Production Plan",
        readonly=True,
    )

    plan_mou_id = fields.Many2one(
        related="production_plan_id.mou_id",
        string="No. MOU",
    )

    plan_brand_name = fields.Char(
        related="production_plan_id.brand_name",
        string="Nama Brand",
    )

    production_plan_line_id = fields.Many2one(
        "mrp.production.plan.line",
        string="Production Plan Line",
    )

    production_plan_product_line_id = fields.Many2one(
        "mrp.production.plan.product.line",
        string="Production Plan Product",
        ondelete="set null",
    )

    def button_mark_done(self):
        """Perintah Produksi dari plan bertahap hanya boleh selesai lewat tahap Packing (setelah QC lulus)."""
        if not self.env.context.get("stage_flow_done"):
            for order in self:
                stages = order.production_plan_product_line_id.stage_ids
                pending = stages.filtered(lambda s: s.state != "done")
                if pending:
                    raise UserError(
                        f"{order.name} belum bisa diselesaikan: proses produksi belum selesai. "
                        f"Tahap yang belum selesai: {', '.join(pending.sorted('sequence').mapped('stage_id.name'))}. "
                        "Jalankan tahap dari tab Proses Produksi. Perintah Produksi selesai otomatis "
                        "setelah tahap terakhir lulus QC."
                    )
        return super().button_mark_done()

    def action_open_production_plan(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Production Plan",
            "res_model": "mrp.production.plan",
            "view_mode": "form",
            "res_id": self.production_plan_id.id,
            "target": "current",
        }

    stage_ids = fields.One2many(
        "mrp.production.plan.stage",
        "production_id",
        string="Proses Produksi",
    )

    plan_sibling_mo_ids = fields.Many2many(
        "mrp.production",
        compute="_compute_plan_sibling_mo_ids",
        string="Produk Lain di Plan",
    )

    @api.depends("production_plan_id.manufacturing_order_ids")
    def _compute_plan_sibling_mo_ids(self):
        for mo in self:
            mo.plan_sibling_mo_ids = mo.production_plan_id.manufacturing_order_ids - mo
