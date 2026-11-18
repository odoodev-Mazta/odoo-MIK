from odoo import api, fields, models

PROCESS_STATES = [("done", "Done"), ("progress", "Progress")]
PO_STATUS = [
    ("selesai", "Selesai"),
    ("progress", "Progress"),
    ("partial", "Partial"),
    ("closing", "Closing"),
]
# Status PO gabungan: satu produk masih jalan -> PO masih jalan.
STATUS_PRIORITY = ["progress", "partial", "closing", "selesai"]


class ProductionReport(models.Model):
    """Laporan Produksi (Excel): satu data per No. PO, berisi banyak produk (seperti Plan Produksi)."""
    _name = "mrp.production.report"
    _description = "Laporan Produksi (Excel)"
    _order = "po_date desc, id desc"
    _rec_name = "display_label"

    po_number = fields.Char(string="No. PO", index=True)
    po_date = fields.Date(string="Tgl PO")
    line_ids = fields.One2many("mrp.production.report.line", "report_id", string="Produk")
    brand = fields.Char(string="Brand", compute="_compute_summary", store=True)
    product_count = fields.Integer(string="Jumlah Produk", compute="_compute_summary", store=True)
    qty_total = fields.Float(string="Total Qty (pcs)", compute="_compute_summary", store=True)
    material_total = fields.Float(string="Total Bahan (gr)", compute="_compute_summary", store=True)
    production_date = fields.Date(string="Tgl Produksi Awal", compute="_compute_summary", store=True)
    delivery_date = fields.Date(string="Tgl Kirim Terakhir", compute="_compute_summary", store=True)
    po_status = fields.Selection(PO_STATUS, string="Status PO", compute="_compute_summary", store=True, index=True)
    lead_days = fields.Integer(
        string="Lama PO s/d Kirim (hari)", compute="_compute_summary", store=True, aggregator="avg",
    )
    display_label = fields.Char(string="Produksi", compute="_compute_display_label", store=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, index=True)

    def init(self):
        # Versi pertama menyimpan satu baris Excel per data (tanpa rincian produk).
        # Data lama itu dibuang supaya bisa diimport ulang dalam bentuk per PO.
        self.env.cr.execute("""
            SELECT 1 FROM information_schema.columns
             WHERE table_name = 'mrp_production_report' AND column_name = 'product_type'
        """)
        if self.env.cr.fetchone():
            self.env.cr.execute("DELETE FROM mrp_production_report")
            for column in ("sequence_label", "batch_no", "product_type", "qty", "packaging", "unit_weight",
                           "total_material", "mixing_state", "filling_state", "labeling_state",
                           "packing_state", "delivery_state", "ready_date"):
                self.env.cr.execute(f'ALTER TABLE mrp_production_report DROP COLUMN IF EXISTS "{column}"')

    @api.depends(
        "po_date", "line_ids.brand", "line_ids.qty", "line_ids.total_material", "line_ids.production_date",
        "line_ids.delivery_date", "line_ids.po_status",
    )
    def _compute_summary(self):
        for rec in self:
            lines = rec.line_ids
            rec.brand = ", ".join(dict.fromkeys(b for b in lines.mapped("brand") if b)) or False
            rec.product_count = len(lines)
            rec.qty_total = sum(lines.mapped("qty"))
            rec.material_total = sum(lines.mapped("total_material"))
            productions = [d for d in lines.mapped("production_date") if d]
            deliveries = [d for d in lines.mapped("delivery_date") if d]
            rec.production_date = min(productions) if productions else False
            rec.delivery_date = max(deliveries) if deliveries else False
            statuses = set(lines.mapped("po_status"))
            rec.po_status = next((s for s in STATUS_PRIORITY if s in statuses), False)
            rec.lead_days = (rec.delivery_date - rec.po_date).days if rec.po_date and rec.delivery_date else 0

    @api.depends("po_number", "brand")
    def _compute_display_label(self):
        for rec in self:
            label = f"PO {rec.po_number}" if rec.po_number else "Tanpa No. PO"
            rec.display_label = f"{label} · {rec.brand}" if rec.brand else label


class ProductionReportLine(models.Model):
    """Satu produk di dalam satu PO (satu baris Excel)."""
    _name = "mrp.production.report.line"
    _description = "Produk Laporan Produksi (Excel)"
    _order = "report_id, sequence, id"

    report_id = fields.Many2one("mrp.production.report", string="No. PO", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    sequence_label = fields.Char(string="Urutan Produksi")
    batch_no = fields.Char(string="No. Batch", index=True)
    brand = fields.Char(string="Brand")
    product_type = fields.Char(string="Jenis Produk", index=True)
    qty = fields.Float(string="Qty (pcs)")
    packaging = fields.Char(string="Jenis Kemasan")
    unit_weight = fields.Float(string="Satuan Berat (gr)")
    total_material = fields.Float(string="Total Bahan (gr)")
    production_date = fields.Date(string="Tgl Produksi")
    mixing_state = fields.Selection(PROCESS_STATES, string="Mixing")
    filling_state = fields.Selection(PROCESS_STATES, string="Filling")
    labeling_state = fields.Selection(PROCESS_STATES, string="Labeling & Coding")
    packing_state = fields.Selection(PROCESS_STATES, string="Packing")
    delivery_state = fields.Selection(PROCESS_STATES, string="Kirim")
    ready_date = fields.Date(string="Tgl Siap Produksi")
    delivery_date = fields.Date(string="Tgl Kirim")
    po_status = fields.Selection(PO_STATUS, string="Status")
    po_number = fields.Char(related="report_id.po_number", string="No. PO (teks)", store=True)
    po_date = fields.Date(related="report_id.po_date", string="Tgl PO", store=True)

    def _import_key(self):
        self.ensure_one()
        return tuple(
            (value or "").strip().upper()
            for value in (self.brand, self.product_type, self.packaging, self.batch_no)
        )
