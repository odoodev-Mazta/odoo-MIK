from odoo import models, fields, api
from odoo.exceptions import ValidationError
from markupsafe import Markup


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    marketing_sequence = fields.Char(
        string='No. PO Produksi',
        copy=False,
        index=True,
    )

    production_plan_ids = fields.One2many(
        'mrp.production.plan',
        'sale_order_id',
        string='Production Planning',
    )

    production_status = fields.Selection(
        [
            ('not_sent', 'Not Sent'),
            ('sent', 'Sent to Production'),
            ('planned', 'Production Planned'),
            ('running', 'Production Running'),
            ('done', 'Production Done'),
        ],
        string='Production Status',
        default='not_sent',
        copy=False,
    )

    def action_send_to_production(self):
        for order in self:

            if not order.marketing_sequence:
                raise ValidationError(
                    "No. PO Produksi harus diisi terlebih dahulu."
                )

            if order.production_plan_ids:
                raise ValidationError(
                    "Sales Order ini sudah memiliki Production Planning."
                )

            production_lines = order.order_line.filtered(
                lambda line: not line.display_type and line.product_id
            )

            if not production_lines:
                raise ValidationError(
                    "Sales Order belum memiliki produk."
                )

            plan = self.env["mrp.production.plan"].create({
                "sale_order_id": order.id,
                "production_po_number": order.marketing_sequence,
            })

            for sequence, line in enumerate(
                    production_lines,
                    start=1
            ):
                self.env["mrp.production.plan.product.line"].create({
                    "plan_id": plan.id,
                    "sequence": sequence * 10,
                    "product_id": line.product_id.id,
                    "product_qty": line.product_uom_qty,
                })

            order.production_status = "sent"

            order.message_post(
                body=Markup(
                    "<p><b>Production request telah dikirim.</b></p>"
                    f"<p><b>No. PO Produksi:</b> "
                    f"{order.marketing_sequence}</p>"
                    "<p><b>Production Planning:</b></p>"
                    f"<ul><li>{plan.name}</li></ul>"
                )
            )

        return True