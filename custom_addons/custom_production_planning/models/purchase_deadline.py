from odoo import api, fields, models


def _deadline_for(env, sale_order):
    """Tanggal mulai produksi paling awal dari plan aktif milik SO."""
    if not sale_order:
        return False
    plans = env["mrp.production.plan"].search([
        ("sale_order_id", "=", sale_order.id), ("state", "!=", "cancel"),
    ])
    starts = [d for d in plans.product_line_ids.mapped("production_start") if d]
    return min(starts) if starts else False


class PurchaseRequest(models.Model):
    _inherit = "purchase.request"

    production_deadline = fields.Date(string="Mulai Produksi", compute="_compute_arrival_warning")
    arrival_warning = fields.Char(compute="_compute_arrival_warning")

    @api.depends("sale_order_id", "estimated_date")
    def _compute_arrival_warning(self):
        for request in self:
            deadline = _deadline_for(self.env, request.sale_order_id)
            request.production_deadline = deadline
            late = deadline and request.estimated_date and request.estimated_date > deadline
            request.arrival_warning = (
                f"Estimasi barang tiba {request.estimated_date:%d/%m/%Y} lebih lambat dari jadwal mulai produksi "
                f"{deadline:%d/%m/%Y}. Produksi tidak bisa jalan tanpa bahan."
            ) if late else False


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    production_deadline = fields.Date(string="Mulai Produksi", compute="_compute_arrival_warning")
    arrival_warning = fields.Char(compute="_compute_arrival_warning")

    @api.depends("sale_order_id", "date_planned")
    def _compute_arrival_warning(self):
        for order in self:
            deadline = _deadline_for(self.env, order.sale_order_id)
            order.production_deadline = deadline
            arrival = order.date_planned.date() if order.date_planned else False
            late = deadline and arrival and arrival > deadline
            order.arrival_warning = (
                f"Barang dijadwalkan tiba {arrival:%d/%m/%Y} lebih lambat dari jadwal mulai produksi "
                f"{deadline:%d/%m/%Y}. Produksi tidak bisa jalan tanpa bahan."
            ) if late else False
