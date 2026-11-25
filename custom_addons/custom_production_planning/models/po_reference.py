import base64
import difflib
import io
import re

from odoo import api, fields, models

from . import history_product


def _norm(value):
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def po_key(value):
    """'004' / '04' / 4 -> '4'. Nomor PO di Excel ditulis dengan nol di depan yang berbeda-beda."""
    digits = re.sub(r"\D", "", str(value or ""))
    return str(int(digits)) if digits else ""


class ProductionPoReference(models.Model):
    """Daftar 'PO MIK' (Excel BOM): per nomor PO/SO, nama produk jadi yang benar, jenis, qty, dan kemasan.
    Dipakai sebagai nama baku produk saat mencocokkan Excel produksi dan Surat Jalan."""
    _name = "mrp.production.po.ref"
    _inherit = ["history.table.guard"]
    _description = "Referensi PO MIK (Nama Produk Baku)"
    _order = "po_date desc, id"

    po_key = fields.Char(string="No. PO", index=True)
    po_date = fields.Date(string="Tanggal")
    product_name = fields.Char(string="Nama Produk Jadi", required=True)
    kind_key = fields.Char(string="Jenis (kunci)", index=True)
    kind_name = fields.Char(string="Jenis Produk")
    qty = fields.Float(string="Qty")
    packaging = fields.Char(string="Jenis Kemasan")
    component_count = fields.Integer(string="Jumlah Komponen BOM")

    # ------------------------------------------------------------------
    # Import dari file "PO MIK"
    # ------------------------------------------------------------------
    @api.model
    def looks_like_po_ref_file(self, file_b64):
        from openpyxl import load_workbook

        try:
            workbook = load_workbook(io.BytesIO(base64.b64decode(file_b64)), data_only=True, read_only=True)
        except Exception:
            return False
        for sheet in workbook.worksheets:
            for index, values in enumerate(sheet.iter_rows(values_only=True)):
                if index > 6:
                    break
                keys = {_norm(cell) for cell in values}
                if "NOSO" in keys and "PRODUCT" in keys and "BOMLINESCOMPONENT" in keys:
                    return True
        return False

    @api.model
    def import_file(self, file_b64):
        from openpyxl import load_workbook

        workbook = load_workbook(io.BytesIO(base64.b64decode(file_b64)), data_only=True, read_only=True)
        rows = []
        for sheet in workbook.worksheets:
            header = None
            current = None
            for values in sheet.iter_rows(values_only=True):
                cells = [_norm(c) for c in values]
                if header is None:
                    if "NOSO" in cells and "PRODUCT" in cells:
                        header = cells
                        idx_so, idx_product = cells.index("NOSO"), cells.index("PRODUCT")
                        idx_kind = cells.index("JENISPRODUK") if "JENISPRODUK" in cells else None
                        idx_qty = cells.index("QTY") if "QTY" in cells else None
                        qty_cols = [i for i, c in enumerate(cells) if c == "QTY"]
                        idx_pack = cells.index("JENISKEMASAN") if "JENISKEMASAN" in cells else None
                        idx_date = next((i for i, c in enumerate(cells) if c in ("TGL", "TANGGAL")), None)
                        idx_comp = next((i for i, c in enumerate(cells) if c == "BOMLINESCOMPONENT"), None)
                    continue
                if values[idx_product]:
                    kind = values[idx_kind] if idx_kind is not None else next(
                        (values[i] for i in qty_cols if isinstance(values[i], str)), None
                    )
                    date = values[idx_date] if idx_date is not None else None
                    current = {
                        "po_key": po_key(values[idx_so]),
                        "product_name": re.sub(r"\s+", " ", str(values[idx_product]).replace("\n", " ")).strip(),
                        "kind_key": history_product.kind_key(kind),
                        "kind_name": str(kind).strip() if kind else False,
                        "qty": values[idx_qty] if idx_qty is not None and isinstance(values[idx_qty], (int, float)) else 0.0,
                        "packaging": str(values[idx_pack]).strip() if idx_pack is not None and values[idx_pack] else False,
                        "po_date": date.date() if hasattr(date, "date") else False,
                        "component_count": 0,
                    }
                    rows.append(current)
                elif current is not None and idx_comp is not None and values[idx_comp]:
                    current["component_count"] += 1
        existing = {(r.po_key, _norm(r.product_name), r.kind_key): r for r in self.search([])}
        created = updated = 0
        for vals in rows:
            key = (vals["po_key"], _norm(vals["product_name"]), vals["kind_key"])
            record = existing.get(key)
            if record:
                record.write(vals)
                updated += 1
            else:
                existing[key] = self.create(vals)
                created += 1
        return created, updated

    @api.model
    def import_and_refresh(self, file_b64):
        """Import file PO MIK, lalu cocokkan ulang baris Excel yang belum jadi Plan / Delivery dengan nama baku."""
        created, updated = self.import_file(file_b64)
        self.env.flush_all()
        lines = self.env["mrp.production.report.line"].search([("plan_id", "=", False)])
        lines.action_auto_match()
        lines._compute_proposed_product_name()
        recaps = self.env["mrp.delivery.recap"].search([("picking_id", "=", False)])
        recaps.action_auto_match()
        recaps._compute_proposed_product_name()
        return created, updated

    # ------------------------------------------------------------------
    # Pencarian nama baku
    # ------------------------------------------------------------------
    @api.model
    def canonical_for_production(self, po_number, kind, brand_texts, qty=0.0):
        """Nama produk jadi untuk baris Excel produksi: nomor PO + jenis produk, brand harus mirip."""
        key, kind_key = po_key(po_number), history_product.kind_key(kind)
        if not key or not kind_key:
            return False
        refs = self.search([("po_key", "=", key), ("kind_key", "=", kind_key)])
        brands = {_norm(b) for b in brand_texts if b} - {""}

        def brand_ok(ref):
            name = _norm(ref.product_name)
            return not brands or any(
                b in name or difflib.SequenceMatcher(None, b, name[: len(b)]).ratio() >= 0.8 for b in brands
            )

        good = refs.filtered(brand_ok)
        if len(good) > 1 and qty:
            same_qty = good.filtered(lambda r: abs(r.qty - qty) < 0.5)
            good = same_qty or good
        return good[:1].product_name or False

    @api.model
    def canonical_for_delivery(self, po_number, raw_name):
        """Nama produk jadi untuk Surat Jalan: dari PO yang sama, nama yang paling mirip dan ukurannya sama."""
        key = po_key(po_number)
        if not key or not raw_name:
            return False
        name_key = _norm(re.sub(r"\(.*?\)", "", str(raw_name)))
        best, best_ratio = False, 0.0
        digits = "".join(re.findall(r"\d+", name_key))
        for ref in self.search([("po_key", "=", key)]):
            ref_key = _norm(ref.product_name)
            if "".join(re.findall(r"\d+", ref_key)) != digits:
                continue
            ratio = difflib.SequenceMatcher(None, name_key, ref_key).ratio()
            if ratio > best_ratio:
                best, best_ratio = ref.product_name, ratio
        return best if best_ratio >= 0.75 else False
