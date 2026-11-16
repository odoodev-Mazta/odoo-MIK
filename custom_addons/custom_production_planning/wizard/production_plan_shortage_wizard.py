from markupsafe import Markup, escape

from odoo import api, fields, models


class ProductionPlanShortageWizard(models.TransientModel):
    _name = "mrp.production.plan.shortage.wizard"
    _description = "Konfirmasi Plan Produksi dengan Stok Kurang"

    plan_id = fields.Many2one("mrp.production.plan", required=True, readonly=True)
    shortage_html = fields.Html(compute="_compute_shortage_html", sanitize=False)

    @api.depends("plan_id.material_shortage_ids.shortage_qty")
    def _compute_shortage_html(self):
        for wiz in self:
            rows = wiz.plan_id.material_shortage_ids.filtered(lambda s: s.shortage_qty > 0)
            body = Markup("").join(
                Markup("<tr><td>%s</td><td>%s</td><td class='text-end'>%g</td>"
                       "<td class='text-end'>%g</td><td class='text-end text-danger'>%g</td></tr>")
                % (
                    s.finished_product_id.display_name or "",
                    s.product_id.display_name or "",
                    s.required_qty, s.available_qty, s.shortage_qty,
                )
                for s in rows
            )
            wiz.shortage_html = Markup(
                "<table class='table table-sm'><thead><tr><th>Produk Jadi</th><th>Bahan</th>"
                "<th class='text-end'>Dibutuhkan</th><th class='text-end'>Stok</th>"
                "<th class='text-end'>Kurang</th></tr></thead><tbody>%s</tbody></table>"
            ) % body

    def action_confirm(self):
        self.ensure_one()
        return self.plan_id.with_context(skip_shortage_confirm=True).action_generate_stages()
