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
    def _bom_index(self):
        """({no PO: [nama produk BoM]}, [semua nama produk BoM]). Kode BoM bentuknya 'SO-088', 'SO-0120', 'SO-;011'."""
        cache = self.env.cr.cache
        if "po_ref_bom_index" not in cache:
            by_po, every, seen, counts = {}, [], set(), {}
            for bom in self.env["mrp.bom"].search([]):
                name = bom.product_tmpl_id.name
                if not name:
                    continue
                counts[name] = counts.get(name, 0) + 1
                if name not in seen:
                    seen.add(name)
                    every.append(name)
                match = re.match(r"\s*SO\D*(\d+)", bom.code or "", re.I)
                if match:
                    pool = by_po.setdefault(po_key(match.group(1)), [])
                    if name not in pool:
                        pool.append(name)
            cache["po_ref_bom_index"] = (by_po, every, counts)
        return cache["po_ref_bom_index"]

    @api.model
    def _bom_names(self, key):
        return self._bom_index()[0].get(key, [])

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
        if good:
            return good[0].product_name
        # Cadangan: BoM di Odoo dengan kode SO-<no PO>; jenis produk harus ada di namanya.
        found = [
            n for n in self._bom_names(key)
            if kind_key in _norm(n) and (not brands or any(b in _norm(n) for b in brands))
        ]
        return found[0] if len(found) == 1 else False

    _GENERIC_WORDS = {"DR", "DRG", "DRA", "SKINCARE", "SKIN", "BY", "THE", "SPF", "PA", "NEW"}
    _WORD_ALIAS = {"MASKER": "MASK", "DECONGEL": "DECON"}

    @api.model
    def _name_parts(self, text):
        """(ukuran, [kata penting berurutan]). 'dr. Farina Decon Gel 15 gr' -> ('15', ['FARINA','DECON','GEL'])."""
        text = re.sub(r"\(.*?\)", " ", str(text or "")).upper()
        sizes = re.findall(r"(\d+(?:[.,]\d+)?)\s*(?:GR|GRAM|G|ML)\b", text)
        size = sizes[-1].replace(",", ".") if sizes else ""
        text = re.sub(r"\d+(?:[.,]\d+)?\s*(?:GR|GRAM|G|ML)\b", " ", text)
        out = []
        for word in re.findall(r"[A-Z]{2,}", text):
            word = self._WORD_ALIAS.get(word, word)
            if word not in self._GENERIC_WORDS:
                out.append(word)
        return size, out

    @staticmethod
    def _word_in(word, words, joined):
        """Kata cocok bila sama, terkandung (spasi beda: DERMA TEA = DERMATEA), atau salah ketik satu huruf."""
        if word in words or (len(word) >= 3 and word in joined):
            return True
        for other in words:
            ratio = difflib.SequenceMatcher(None, word, other).ratio()
            if ratio >= 0.8 or (len(word) == len(other) >= 3 and word[0] == other[0] and ratio >= 0.66):
                return True
        return False

    @api.model
    def canonical_for_delivery(self, po_number, raw_name):
        """Nama produk jadi (mengikuti BoM / PO MIK) untuk satu baris Surat Jalan.

        Yang diabaikan: awalan 'Dr.', kata umum, huruf besar/kecil, spasi, tanda baca, salah ketik satu huruf.
        Netto di SJ sering kosong, jadi ukuran hanya dipakai bila dicantumkan.
        Dalam PO yang sama: brand cocok dan kandidat unik -> dipakai. Tanpa PO: cari di semua BoM, harus unik."""
        raw_size, raw_words = self._name_parts(raw_name)
        if not raw_words:
            return False
        brand, rest = raw_words[0], raw_words[1:]
        key = po_key(po_number)
        by_po, every, counts = self._bom_index()
        word_in = self._word_in

        def rows_for(names):
            rows = []
            for name in names:
                size, words = self._name_parts(name)
                joined = "".join(words)
                if not word_in(brand, set(words), joined):
                    continue
                hit = sum(1 for w in rest if word_in(w, set(words), joined))
                overlap = hit / len(rest) if rest else 1.0
                size_ok = not raw_size or not size or size == raw_size
                rows.append({"name": name, "overlap": overlap, "extra": len(words) - 1 - hit, "size_ok": size_ok})
            return rows

        def unique_best(rows):
            if not rows:
                return False
            rows = sorted(rows, key=lambda r: (-r["overlap"], r["extra"]))
            top = [r for r in rows if (r["overlap"], r["extra"]) == (rows[0]["overlap"], rows[0]["extra"])]
            if len(top) == 1:
                return top[0]["name"]
            # sama persis kecuali ukuran: ambil yang BoM-nya paling banyak (jelas dominan)
            top.sort(key=lambda r: -counts.get(r["name"], 0))
            if counts.get(top[0]["name"], 0) >= 2 * max(counts.get(top[1]["name"], 0), 1):
                return top[0]["name"]
            return False

        if key:
            names = self.search([("po_key", "=", key)]).mapped("product_name")
            names += [n for n in by_po.get(key, []) if n not in names]
            rows = rows_for(names)
            same = [r for r in rows if r["size_ok"]]
            if len(same) == 1:
                return same[0]["name"]
            found = unique_best([r for r in same if r["overlap"] >= 0.5]) if same else False
            if found:
                return found
            found = unique_best([r for r in rows if r["overlap"] == 1.0])
            if found:
                return found
        rows = [r for r in rows_for(every) if r["overlap"] == 1.0 and r["size_ok"]]
        return unique_best(rows) or False
