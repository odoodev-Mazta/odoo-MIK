import re

from odoo import api, fields, models
from odoo.exceptions import UserError

from . import history_product
from .production_report import _similar


def _norm(value):
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


class DeliveryRecap(models.Model):
    """Rekapan Surat Jalan (Excel): riwayat pengiriman, satu baris per barang. Tidak menggerakkan stok."""
    _name = "mrp.delivery.recap"
    _description = "Rekapan Surat Jalan (Excel)"
    _order = "delivery_date desc, sj_number desc, id"
    _rec_name = "sj_number"

    sj_number = fields.Char(string="No. Surat Jalan", index=True)
    po_number = fields.Char(string="No. PO (Excel)", index=True)
    batch_text = fields.Char(string="No. Batch / ED")
    product_name = fields.Char(string="Nama Barang", index=True)
    qty = fields.Float(string="Jumlah")
    unit = fields.Char(string="Satuan")
    packing = fields.Char(string="Jumlah Packing")
    price = fields.Float(string="Harga")
    value = fields.Float(string="Nilai")
    delivery_date = fields.Date(string="Tgl Kirim", index=True)
    expedition = fields.Char(string="Ekspedisi")
    note = fields.Char(string="Keterangan")
    recipient = fields.Char(string="Penerima")
    phone = fields.Char(string="No. Telp")
    address = fields.Text(string="Alamat")
    sheet_name = fields.Char(string="Sheet")

    brand_id = fields.Many2one("registrasi.brand", string="Brand Terdaftar", index=True)
    is_internal = fields.Boolean(string="Produksi Sendiri", index=True)
    sale_order_id = fields.Many2one(
        "sale.order", string="Sales Order", index=True,
        help="Diisi otomatis bila MOU brand ini hanya punya satu Sales Order, atau pilih manual.",
    )
    product_tmpl_id = fields.Many2one("product.template", string="Produk Odoo")
    picking_id = fields.Many2one(
        "stock.picking", string="Delivery Order", readonly=True, copy=False, index=True, ondelete="set null",
        help="Delivery Order riwayat (Inventory > Operations > Deliveries) yang dibuat dari baris ini.",
    )
    mou_id = fields.Many2one("draft.maklon", string="MOU", compute="_compute_mou_id", store=True, index=True)
    match_state = fields.Selection(
        [("matched", "Terhubung"), ("internal", "Produksi Sendiri"), ("pending", "Perlu Dipasangkan")],
        string="Status Hubungan", compute="_compute_match_state", store=True, index=True,
    )
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, index=True)

    @api.depends("brand_id.mou_id", "sale_order_id.mou_id", "is_internal")
    def _compute_mou_id(self):
        for rec in self:
            rec.mou_id = False if rec.is_internal else (rec.sale_order_id.mou_id or rec.brand_id.mou_id)

    @api.depends("brand_id", "is_internal")
    def _compute_match_state(self):
        for rec in self:
            rec.match_state = "internal" if rec.is_internal else "matched" if rec.brand_id else "pending"

    def _import_key(self):
        self.ensure_one()
        return tuple(_norm(v) for v in (self.sj_number, self.product_name, self.batch_text))

    # ------------------------------------------------------------------
    # Pencocokan otomatis
    # ------------------------------------------------------------------
    @api.model
    def _batch_index(self):
        """No. batch di Laporan Produksi -> (brand, internal). Batch yang sama berarti brand yang sama."""
        index = {}
        for line in self.env["mrp.production.report.line"].search([("batch_no", "!=", False)]):
            if not (line.brand_id or line.is_internal):
                continue
            for part in re.split(r"[&,/]", line.batch_no or ""):
                key = _norm(part)
                if len(key) >= 5:
                    index.setdefault(key, (line.brand_id, line.is_internal))
        return index

    def action_auto_match(self):
        brand_keys = {}
        for brand in self.env["registrasi.brand"].search([]):
            brand_keys.setdefault(_norm(brand.brand_name), (brand, False))
        for alias in self.env["mrp.production.report.brand.alias"].search([]):
            brand_keys[alias.name_key] = (alias.brand_id, alias.is_internal)
        batches = self._batch_index()
        products = {
            _norm(p.name): p for p in self.env["product.template"].search([("sale_ok", "=", True)])
        }
        for rec in self:
            if not rec.is_internal and not rec.brand_id:
                brand, internal = False, False
                token = _norm((rec.batch_text or "").split("/")[0])
                if token in batches:
                    brand, internal = batches[token]
                else:
                    name_key = _norm(rec.product_name)
                    best = max(
                        (key for key in brand_keys if len(key) >= 3 and name_key.startswith(key)),
                        key=len, default=False,
                    )
                    if best:
                        brand, internal = brand_keys[best]
                if internal:
                    rec.is_internal = True
                elif brand:
                    rec.brand_id = brand
            if not rec.product_tmpl_id and rec.product_name:
                key = _norm(re.sub(r"\(.*?\)", "", rec.product_name))
                found = products.get(key)
                if not found and key:
                    similar = [p for name, p in products.items() if len(name) > 8 and (key in name or name in key)]
                    found = similar[0] if len(similar) == 1 else False
                if found:
                    rec.product_tmpl_id = found
            if not rec.sale_order_id and rec.po_number and not rec.is_internal:
                digits = re.sub(r"\D", "", rec.po_number)
                if digits:
                    order = self.env["sale.order"].search(
                        [("name", "in", [f"S{int(digits):05d}", f"S{int(digits):04d}"]), ("state", "=", "sale")], limit=1
                    )
                    names = {_norm(rec.brand_id.brand_name), _norm(rec.product_name)} - {""}
                    order_names = {_norm(order.brand_name), _norm(order.partner_id.name)} - {""}
                    if order and (
                        (rec.mou_id and order.mou_id == rec.mou_id)
                        or any(_similar(n, o) or (o and o in n) for n in names for o in order_names)
                    ):
                        rec.sale_order_id = order
            if rec.mou_id and not rec.sale_order_id:
                orders = self.env["sale.order"].search([("mou_id", "=", rec.mou_id.id), ("state", "=", "sale")], limit=2)
                if len(orders) == 1:
                    rec.sale_order_id = orders
        return True

    def action_create_history_pickings(self):
        """Buat Delivery Order berstatus Done di Inventory > Deliveries, satu per Nomor SJ (dan MOU).

        Hanya riwayat: tanpa reservasi dan tanpa baris pergerakan stok, jadi stok TIDAK berubah.
        Baris yang belum terhubung ke MOU / Produk Odoo dilewati.
        """
        Picking = self.env["stock.picking"].with_context(tracking_disable=True)
        company = self.env.company
        ptype = self.env["stock.picking.type"].search(
            [("code", "=", "outgoing"), ("company_id", "=", company.id)], limit=1
        )
        if not ptype:
            raise UserError("Belum ada tipe operasi Delivery Orders untuk perusahaan ini.")
        customers = self.env.ref("stock.stock_location_customers")
        index = history_product.product_index(self.env)
        rows = self.search([("picking_id", "=", False)]) if not self else self
        rows = rows.filtered(lambda r: not r.picking_id and r.sj_number and r.product_name)
        for rec in rows.filtered(lambda r: not r.product_tmpl_id):
            rec.product_tmpl_id = history_product.find_or_create_product(
                self.env, history_product.clean_name(rec.product_name), index
            )
        self._learn_product_pairs(index)
        groups = {}
        for rec in rows.sorted("id"):
            key = (_norm(rec.sj_number), rec.mou_id.id)
            groups[key] = groups.get(key, self.browse()) | rec
        created = 0
        for (sj_key, mou_id), recs in groups.items():
            first = recs[0]
            order = recs.sale_order_id[:1]
            name = first.sj_number.strip()
            same_sj = len({k for k in groups if k[0] == sj_key}) > 1
            if same_sj:
                name = f"{name} ({first.brand_id.brand_name or first.mou_id.draft_name})"
            if Picking.search_count([("name", "=", name), ("company_id", "=", company.id)]):
                name = f"{name} #{first.id}"
            done_date = fields.Datetime.to_datetime(first.delivery_date) if first.delivery_date else fields.Datetime.now()
            picking = Picking.create({
                "name": name,
                "picking_type_id": ptype.id,
                "partner_id": first.mou_id.nama_cust.id or False,
                "location_id": ptype.default_location_src_id.id,
                "location_dest_id": customers.id,
                "origin": " / ".join(filter(None, [
                    order.name,
                    f"PO {first.po_number}" if first.po_number else False,
                ])) or "Rekapan Surat Jalan",
                "sale_id": order.id or False,
                "scheduled_date": done_date,
                "mou_id": first.mou_id.id or False,
                "note": "Riwayat dari Rekapan Surat Jalan (Excel). Stok tidak berubah.",
                "move_ids": [(0, 0, {
                    "product_id": rec.product_tmpl_id.product_variant_id.id,
                    "description_picking": rec.product_name or False,
                    "product_uom_qty": rec.qty,
                    "product_uom": rec.product_tmpl_id.uom_id.id,
                    "location_id": ptype.default_location_src_id.id,
                    "location_dest_id": customers.id,
                    "product_hna": rec.price,
                }) for rec in recs],
            })
            self.env.flush_all()
            # Langsung Done tanpa _action_done: tidak ada quant / move line, jadi stok tidak tersentuh.
            self.env.cr.execute(
                "UPDATE stock_move SET state='done', quantity=product_uom_qty, picked=true, date=%s WHERE id = ANY(%s)",
                (done_date, picking.move_ids.ids),
            )
            self.env.cr.execute(
                "UPDATE stock_picking SET state='done', date_done=%s WHERE id=%s", (done_date, picking.id)
            )
            self.env.invalidate_all()
            recs.write({"picking_id": picking.id})
            created += 1
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Delivery Riwayat",
                "message": f"{created} Delivery Order riwayat dibuat di Inventory > Deliveries.",
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    def _learn_product_pairs(self, index):
        """Surat Jalan menulis jenisnya, mis. 'Miuna Aging Care Mask (Masker Aging)': brand + jenis -> produk.
        Hanya dipelajari bila produknya memang sudah ada di Odoo (bukan yang baru dibuat)."""
        Alias = self.env["mrp.production.report.product.alias"]
        for rec in self.filtered(lambda r: r.brand_id and r.product_tmpl_id and r.product_name):
            kind = history_product.kind_from_name(rec.product_name)
            if kind and history_product.find_product(index, history_product.clean_name(rec.product_name)):
                Alias.learn(history_product._norm_brand(rec.brand_id.brand_name), kind, rec.product_tmpl_id)

    @api.model
    def action_rematch(self):
        self.search([]).action_auto_match()
        return {"type": "ir.actions.client", "tag": "reload"}

    def write(self, vals):
        result = super().write(vals)
        if ("brand_id" in vals or "is_internal" in vals) and not self.env.context.get("skip_recap_propagate"):
            for rec in self.filtered(lambda r: r.brand_id or r.is_internal):
                same = self.search([
                    ("id", "!=", rec.id), ("brand_id", "=", False), ("is_internal", "=", False),
                ]).filtered(lambda r: _norm(r.product_name) == _norm(rec.product_name))
                if same:
                    same.with_context(skip_recap_propagate=True).write(
                        {"brand_id": rec.brand_id.id, "is_internal": rec.is_internal}
                    )
        return result


class StockPickingImportWizard(models.TransientModel):
    """Tombol Import di Inventory > Deliveries juga menerima file Rekapan Surat Jalan (Excel)."""
    _inherit = "stock.picking.import.wizard"

    def _is_recap_file(self):
        import base64
        import io

        from openpyxl import load_workbook

        try:
            workbook = load_workbook(io.BytesIO(base64.b64decode(self.file)), data_only=True, read_only=True)
        except Exception:
            return False
        for sheet in workbook.worksheets:
            for index, values in enumerate(sheet.iter_rows(values_only=True)):
                if index > 10:
                    break
                keys = {_norm(cell) for cell in values}
                if "NOMORSJ" in keys and "NAMABARANG" in keys:
                    return True
        return False

    def action_import(self):
        self.ensure_one()
        if self.file and self._is_recap_file():
            recap_wizard = self.env["mrp.delivery.recap.import.wizard"].create(
                {"file": self.file, "filename": self.filename}
            )
            recap_wizard.action_import()
            action = self.env["mrp.delivery.recap"].action_create_history_pickings()
            action["params"]["title"] = "Import Rekapan Surat Jalan"
            action["params"]["message"] = f"{recap_wizard.result}. {action['params']['message']}"
            return action
        return super().action_import()
