import difflib
import re

from odoo import api, fields, models

from . import history_product


def _norm(value):
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _similar(a, b):
    """Nama brand dianggap sama: saling memuat, awalan sama minimal 4 huruf, atau ejaan sangat mirip."""
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    prefix = 0
    for x, y in zip(a, b):
        if x != y:
            break
        prefix += 1
    return prefix >= 4 or difflib.SequenceMatcher(None, a, b).ratio() >= 0.8


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
    sale_order_id = fields.Many2one(
        "sale.order", string="Sales Order", index=True,
        help="Diisi otomatis bila No. PO sama dengan Customer Reference di Sales Order, atau pilih manual. "
             "Bila terisi, MOU diambil dari Sales Order ini.",
    )
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

    @api.model_create_multi
    def create(self, vals_list):
        reports = super().create(vals_list)
        reports._auto_link_sale_order()
        return reports

    def _auto_link_sale_order(self):
        """No. PO di Excel dicocokkan ke Customer Reference Sales Order (bila sudah diisi di sana)."""
        for report in self.filtered(lambda r: r.po_number and not r.sale_order_id):
            order = self.env["sale.order"].search([("client_order_ref", "=ilike", report.po_number)], limit=2)
            if len(order) == 1:
                report.sale_order_id = order
                continue
            # No. PO Excel = nomor SO di Odoo dengan penomoran lain (004 -> S00004). Dipakai hanya bila
            # brand SO itu sama dengan brand di Excel, supaya tidak salah sambung.
            digits = re.sub(r"\D", "", report.po_number)
            if not digits:
                continue
            # Penomoran SO ada dua bentuk: S00004 (lama) dan S0145 (baru).
            order = self.env["sale.order"].search(
                [("name", "in", [f"S{int(digits):05d}", f"S{int(digits):04d}"])], limit=1
            )
            names = {_norm(line.brand_id.brand_name) for line in report.line_ids if line.brand_id} | {
                _norm(line.brand) for line in report.line_ids if line.brand
            }
            order_names = {_norm(order.brand_name), _norm(order.partner_id.name)} - {""}
            if order and any(_similar(n, o) or (n and n in o) for n in names for o in order_names):
                report.sale_order_id = order
                continue
            # Tidak cocok lewat nomor: bila MOU brand ini hanya punya satu Sales Order, pakai itu.
            mous = report.line_ids.mou_id
            if len(mous) == 1:
                orders = self.env["sale.order"].search([("mou_id", "=", mous.id), ("state", "=", "sale")], limit=2)
                if len(orders) == 1:
                    report.sale_order_id = orders

    def action_create_history_plans(self):
        """Buat Plan Produksi riwayat di Production Planning, satu per No. PO (dan MOU).

        Plan riwayat tanpa Perintah Produksi dan tanpa perubahan stok. Sales Order diisi bila ada, bila tidak
        Plan terlacak lewat MOU dari brand (atau tanpa MOU untuk produksi sendiri). Baris yang produk atau
        brand-nya belum dipasangkan dilewati.
        """
        Plan = self.env["mrp.production.plan"].with_context(tracking_disable=True)
        Stage = self.env["mrp.production.plan.stage"].with_context(tracking_disable=True)
        masters = [
            ("penimbangan", self.env.ref("custom_production_planning.stage_penimbangan")),
            ("mixing", self.env.ref("custom_production_planning.stage_mixing")),
            ("filling", self.env.ref("custom_production_planning.stage_filling")),
            ("labeling", self.env.ref("custom_production_planning.stage_labeling")),
            ("packing", self.env.ref("custom_production_planning.stage_packing")),
        ]
        index = history_product.product_index(self.env)
        reports = self or self.search([])
        created = skipped = with_so = 0
        for report in reports.sorted("id"):
            lines = report.line_ids.filtered(lambda l: not l.plan_id)
            usable = lines
            for line in usable.filtered(lambda l: not l.product_tmpl_id):
                brand = line.brand_id.brand_name or line.brand
                name = history_product.standard_name(brand, line.product_type, line.packaging)
                if name:
                    line.product_tmpl_id = history_product.find_or_create_product(self.env, name, index)
            groups = {}
            for line in usable:
                groups.setdefault(line.mou_id.id if not line.is_internal else False, self.env["mrp.production.report.line"])
                groups[line.mou_id.id if not line.is_internal else False] |= line
            for mou_id, group in groups.items():
                po = report.po_number or "TANPA-PO"
                order = report.sale_order_id
                if order and (order.state != "sale" or (mou_id and order.mou_id.id != mou_id)):
                    order = self.env["sale.order"]
                starts = [d for d in group.mapped("production_date") if d]
                ends = [d for d in group.mapped("delivery_date") if d] or starts
                all_done = all(line.po_status == "selesai" or line.packing_state == "done" for line in group)
                plan = Plan.create({
                    "history_po_number": report.po_number or False,
                    "sale_order_id": order.id or False,
                    "is_history": True,
                    "history_mou_id": mou_id or False,
                    "history_brand": group[0].brand_id.brand_name or group[0].brand or False,
                    "origin_type": "lokal",
                    "planned_start": min(starts) if starts else report.po_date,
                    "planned_end": max(ends) if ends else report.po_date,
                    "state": "done" if all_done else "running",
                    "note": f"Riwayat dari Excel. No. PO {po}"
                            + (f", tgl PO {report.po_date}" if report.po_date else "") + ".",
                    "product_line_ids": [(0, 0, line._plan_line_vals(order)) for line in group],
                })
                stage_vals = []
                for line, product_line in zip(group, plan.product_line_ids):
                    states = {
                        "mixing": line.mixing_state, "filling": line.filling_state,
                        "labeling": line.labeling_state, "packing": line.packing_state,
                    }
                    states["penimbangan"] = "done" if "done" in states.values() else False
                    for key, master in masters:
                        value = states.get(key)
                        done = value == "done"
                        stage_vals.append({
                            "plan_id": plan.id,
                            "product_line_id": product_line.id,
                            "stage_id": master.id,
                            "sequence": master.sequence,
                            "date_start": line.production_date,
                            "date_end": line.production_date,
                            "state": "done" if done else "in_progress" if value == "progress" else "todo",
                            "qc_state": "passed" if done else "pending",
                            "qty_good": line.qty if done else 0.0,
                            "batch_no": line.batch_no if key == "mixing" else False,
                        })
                Stage.create(stage_vals)
                group.write({"plan_id": plan.id})
                created += 1
                with_so += 1 if plan.sale_order_id else 0
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Plan Produksi Riwayat",
                "message": f"{created} Plan riwayat dibuat. {with_so} sudah punya Sales Order, "
                           f"{created - with_so} belum (filter: Tanpa Sales Order).",
                "type": "success",
                "sticky": True,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    def action_rematch(self):
        self.env["mrp.production.report.line"].search([]).action_auto_match()
        self.env["mrp.production.report"].search([])._auto_link_sale_order()
        return {"type": "ir.actions.client", "tag": "reload"}

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
    brand_id = fields.Many2one(
        "registrasi.brand", string="Brand Terdaftar", index=True,
        help="Brand di Registrasi Brand. Dipakai untuk menghubungkan baris ini ke MOU dan Tracking MOU.",
    )
    is_internal = fields.Boolean(
        string="Produksi Sendiri", index=True,
        help="Produk sendiri (tanpa MOU), misalnya MAZDERM atau buffer stock.",
    )
    product_tmpl_id = fields.Many2one("product.template", string="Produk Odoo")
    mou_id = fields.Many2one(
        "draft.maklon", string="MOU", compute="_compute_mou_id", store=True, index=True,
    )
    match_state = fields.Selection(
        [("matched", "Terhubung"), ("internal", "Produksi Sendiri"), ("pending", "Perlu Dipasangkan")],
        string="Status Hubungan", compute="_compute_match_state", store=True, index=True,
    )
    proposed_product_name = fields.Char(
        string="Nama Produk Baru", compute="_compute_proposed_product_name", store=True, index=True,
        help="Nama produk yang akan dibuat bila belum ada produk yang cocok.",
    )
    plan_id = fields.Many2one(
        "mrp.production.plan", string="Plan Produksi", readonly=True, copy=False, index=True, ondelete="set null",
        help="Plan riwayat di Production Planning yang dibuat dari baris ini.",
    )
    po_number = fields.Char(related="report_id.po_number", string="No. PO (teks)", store=True)
    po_date = fields.Date(related="report_id.po_date", string="Tgl PO", store=True)

    def _import_key(self):
        self.ensure_one()
        return tuple(
            (value or "").strip().upper()
            for value in (self.brand, self.product_type, self.packaging, self.batch_no)
        )

    @api.depends("brand_id.mou_id", "report_id.sale_order_id.mou_id", "is_internal")
    def _compute_mou_id(self):
        for line in self:
            if line.is_internal:
                line.mou_id = False
            else:
                line.mou_id = line.report_id.sale_order_id.mou_id or line.brand_id.mou_id

    @api.depends("brand_id", "brand", "product_type", "packaging")
    def _compute_proposed_product_name(self):
        for line in self:
            line.proposed_product_name = history_product.standard_name(
                line.brand_id.brand_name or line.brand, line.product_type, line.packaging
            )

    @api.depends("brand_id", "is_internal")
    def _compute_match_state(self):
        for line in self:
            line.match_state = "internal" if line.is_internal else "matched" if line.brand_id else "pending"

    # ------------------------------------------------------------------
    # Pencocokan Brand / Produk
    # ------------------------------------------------------------------
    def _find_brand(self, brands_by_norm, alias_map):
        """Brand Excel -> (brand, internal). Urutan: pasangan tersimpan, nama sama persis, nama yang saling memuat (harus unik)."""
        self.ensure_one()
        key = _norm(self.brand)
        if not key:
            return False, False
        if key in alias_map:
            return alias_map[key]
        if key in brands_by_norm:
            return brands_by_norm[key], False
        found = {
            brand for name, brand in brands_by_norm.items()
            if len(key) >= 4 and len(name) >= 4 and (key in name or name in key)
        }
        if len(found) == 1:
            return found.pop(), False
        return False, False

    def _suggest_product(self):
        """Produk Odoo: nama memuat brand + kata jenis + ukuran kemasan, hanya dipakai bila hasilnya tepat satu."""
        self.ensure_one()
        brand_keys = {_norm(self.brand_id.brand_name), _norm(self.brand)} - {""}
        if not brand_keys:
            return False
        # Jenis di Excel (mis. "MASKER WINE") dipetakan ke kata yang biasa muncul di nama produk jadi
        # ("... WINE POLYPHENOL MASK 20 GR"). Tiap kelompok kata harus ada, salah satu dari pilihannya.
        synonyms = {
            "MASKER": ("MASK",), "SUNCREAM": ("SUN",), "DECONGEL": ("DECON",), "MOISTURIZER": ("MOIST",),
            "WHITENING": ("BALM", "WHITEN"), "BALM": ("BALM",), "FACEWASH": ("FACEWASH", "FACEWASH"),
            "WINE": ("WINE", "VINIFERA", "GRAPE", "POLYPHENOL"),
            "HYAL": ("HYAL", "HYDRA", "HYDRAC", "SOOTHING"),
            "ACNE": ("ACNE", "PORE", "PURIF", "CLEAR", "OIL"),
            "AGING": ("AGING", "FIRMING", "REJUV", "ASTAXANTHIN", "REGENERATING"),
        }
        groups = []
        for token in (self.product_type or "").upper().replace("D2", " ").split():
            if token in synonyms:
                groups.append(synonyms[token])
            elif len(token) >= 4:
                groups.append((_norm(token),))
        size = re.search(r"(\d+)\s*GR", (self.packaging or "").upper())
        size_key = f"{size.group(1)}GR" if size else ""
        candidates = self.env["product.template"].search([("sale_ok", "=", True)]).filtered(
            lambda p: not history_product.is_component(p.name)
            and any(key in _norm(p.name) for key in brand_keys)
            and all(any(word in _norm(p.name) for word in group) for group in groups)
            and (not size_key or size_key in _norm(p.name))
        )
        if len(candidates) > 1:
            # Beberapa cocok: utamakan yang punya BOM (produk jadi), lalu yang namanya diawali brand.
            with_bom = candidates & self.env["mrp.bom"].search([]).product_tmpl_id
            candidates = with_bom or candidates
        if len(candidates) > 1:
            starts = candidates.filtered(lambda p: any(_norm(p.name).startswith(key) for key in brand_keys))
            candidates = starts or candidates
        return candidates if len(candidates) == 1 else False

    def action_auto_match(self):
        brands_by_norm = {}
        for brand in self.env["registrasi.brand"].search([]):
            brands_by_norm.setdefault(_norm(brand.brand_name), brand)
        alias_map = {
            alias.name_key: (alias.brand_id, alias.is_internal)
            for alias in self.env["mrp.production.report.brand.alias"].search([])
        }
        for line in self:
            if not line.is_internal and not line.brand_id:
                brand, internal = line._find_brand(brands_by_norm, alias_map)
                if internal:
                    line.is_internal = True
                elif brand:
                    line.brand_id = brand
            if not line.product_tmpl_id:
                product = line._paired_product() or line._suggest_product()
                if product:
                    line.with_context(skip_product_alias=True).product_tmpl_id = product
        return True

    def _order_product(self, order):
        """Produk asli di Sales Order (mis. 'Wine Polyphenol Modeling Mask') untuk jenis di Excel, bila tepat satu."""
        self.ensure_one()
        words = {
            "WINE": ("WINE", "VINIFERA", "GRAPE", "POLYPHENOL"), "HYAL": ("HYAL", "HYDRA", "SOOTHING"),
            "ACNE": ("ACNE", "PORE", "PURIF", "CLEAR"), "AGING": ("AGING", "FIRMING", "REJUV", "ASTAXANTHIN"),
            "DECONGEL": ("DECON",), "SUNCREAM": ("SUN",), "MOISTURIZER": ("MOIST",),
            "BALM": ("BALM", "WHITEN"), "WHITENING": ("BALM", "WHITEN"), "NIACARE": ("NIACARE",), "GLYCOCARE": ("GLYCO",),
        }
        groups = [
            words[token] for token in (self.product_type or "").upper().replace("D2", " ").split() if token in words
        ]
        if not order or not groups:
            return self.env["product.product"]
        found = order.order_line.product_id.filtered(
            lambda p: all(any(w in _norm(p.name) for w in group) for group in groups)
        )
        return found if len(found) == 1 else self.env["product.product"]

    def _plan_line_vals(self, order):
        """Baris produk Plan: produk asli SO (bila ada) + produk jadi brand."""
        self.ensure_one()
        finished = self.product_tmpl_id.product_variant_id
        original = self._order_product(order)
        vals = {
            "product_id": (original or finished).id,
            "product_qty": self.qty or 1.0,
            "production_start": self.production_date,
            "production_end": self.delivery_date or self.production_date,
        }
        if original and original != finished:
            vals["finished_product_id"] = finished.id
        return vals

    def _brand_key(self):
        self.ensure_one()
        return _norm(self.brand_id.brand_name or self.brand)

    def _paired_product(self):
        """Pasangan tersimpan: brand + jenis produk -> produk jadi."""
        self.ensure_one()
        alias = self.env["mrp.production.report.product.alias"].search([
            ("brand_key", "=", self._brand_key()),
            ("kind_key", "=", history_product.kind_key(self.product_type)),
        ], limit=1)
        return alias.product_tmpl_id

    def _remember_product_pairing(self):
        """Produk yang dipilih manual diingat untuk brand + jenis yang sama (dan dipakai ke baris lain)."""
        Alias = self.env["mrp.production.report.product.alias"]
        for line in self.filtered(lambda l: l.product_tmpl_id and l._brand_key() and l.product_type):
            Alias.learn(line._brand_key(), history_product.kind_key(line.product_type), line.product_tmpl_id)

    def write(self, vals):
        result = super().write(vals)
        if "brand_id" in vals or "is_internal" in vals:
            self._remember_brand_pairing()
        if "product_tmpl_id" in vals and not self.env.context.get("skip_product_alias"):
            self._remember_product_pairing()
        return result

    def _remember_brand_pairing(self):
        """Pasangan manual diingat, lalu dipakai untuk baris lain dengan tulisan brand yang sama."""
        Alias = self.env["mrp.production.report.brand.alias"]
        for line in self.filtered(lambda l: _norm(l.brand) and (l.brand_id or l.is_internal)):
            values = {
                "name": line.brand,
                "brand_id": False if line.is_internal else line.brand_id.id,
                "is_internal": bool(line.is_internal),
            }
            alias = Alias.search([("name_key", "=", _norm(line.brand))], limit=1)
            if alias:
                alias.write(values)
            else:
                Alias.create(values)
            same = self.search([("id", "!=", line.id), ("brand_id", "=", False), ("is_internal", "=", False)]).filtered(
                lambda l: _norm(l.brand) == _norm(line.brand)
            )
            if same:
                same.write({"brand_id": values["brand_id"], "is_internal": values["is_internal"]})


class ProductionReportBrandAlias(models.Model):
    """Ingatan pasangan 'tulisan brand di Excel' -> brand terdaftar (atau produksi sendiri)."""
    _name = "mrp.production.report.brand.alias"
    _description = "Pasangan Brand Excel"
    _order = "name"

    name = fields.Char(string="Tulisan di Excel", required=True)
    name_key = fields.Char(compute="_compute_name_key", store=True, index=True)
    brand_id = fields.Many2one("registrasi.brand", string="Brand Terdaftar")
    is_internal = fields.Boolean(string="Produksi Sendiri")

    _name_key_unique = models.Constraint("unique(name_key)", "Tulisan brand ini sudah punya pasangan.")

    @api.depends("name")
    def _compute_name_key(self):
        for alias in self:
            alias.name_key = _norm(alias.name)


class ProductionReportProductAlias(models.Model):
    """Ingatan pasangan 'brand + jenis produk di Excel' -> produk jadi di Odoo. Diisi otomatis dari pilihan manual
    dan dari keterangan jenis di Surat Jalan, bisa diubah di Manufacturing > Configuration."""
    _name = "mrp.production.report.product.alias"
    _description = "Pasangan Produk Excel"
    _order = "brand_key, kind_key"

    brand_key = fields.Char(string="Brand", required=True, index=True)
    kind_key = fields.Char(string="Jenis Produk", required=True, index=True)
    product_tmpl_id = fields.Many2one("product.template", string="Produk Jadi", required=True, ondelete="cascade")

    _brand_kind_unique = models.Constraint(
        "unique(brand_key, kind_key)", "Brand dan jenis produk ini sudah punya pasangan."
    )

    @api.model
    def learn(self, brand_key, kind_key, product):
        """Simpan pasangan, lalu terapkan ke baris Excel lain yang belum punya produk."""
        if not (brand_key and kind_key and product):
            return
        alias = self.search([("brand_key", "=", brand_key), ("kind_key", "=", kind_key)], limit=1)
        if alias:
            alias.product_tmpl_id = product
        else:
            self.create({"brand_key": brand_key, "kind_key": kind_key, "product_tmpl_id": product.id})
        Line = self.env["mrp.production.report.line"].with_context(skip_product_alias=True)
        pending = Line.search([("product_tmpl_id", "=", False), ("plan_id", "=", False)]).filtered(
            lambda l: l._brand_key() == brand_key and history_product.kind_key(l.product_type) == kind_key
        )
        pending.write({"product_tmpl_id": product.id})
