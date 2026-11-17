import base64
from collections import OrderedDict

from odoo import Command, fields, models
from odoo.exceptions import UserError

from . import bom_excel

BOM_TYPES = {
    "": "normal",
    "normal": "normal",
    "manufacture": "normal",
    "kit": "phantom",
    "phantom": "phantom",
    "manufacturing": "normal",
}

UOM_ALIASES = {
    "pcs": ["pc", "units", "unit"],
    "gr": ["g", "gr", "gram"],
    "g": ["g", "gr", "gram"],
}


def _norm_name(text):
    """Samakan nama: abaikan huruf besar/kecil, spasi, tanda baca."""
    return "".join(ch for ch in str(text or "").lower() if ch.isalnum())


IMPORT_CHUNK = 15  # jumlah BoM per sekali simpan (satu langkah progress bar)


class _DryRun(Exception):
    """Dipakai untuk membatalkan (rollback) tahap pemeriksaan."""


class MrpBomImportWizard(models.TransientModel):
    _name = "mrp.bom.import.wizard"
    _description = "Import BoM dari Excel"

    file = fields.Binary(string="File Excel (.xlsx)")
    filename = fields.Char()
    mode = fields.Selection(
        [
            ("skip", "Lewati BoM yang sudah ada"),
            ("update", "Update BoM yang sudah ada (tambah/ubah baris, tidak menghapus)"),
        ],
        string="Jika BoM sudah ada",
        default="skip",
        required=True,
    )

    def action_download_format(self):
        return self.env["mrp.bom"].action_download_import_format()

    # ------------------------------------------------------------------
    # Tahap 1: baca dan periksa semua baris (belum ada yang disimpan)
    # ------------------------------------------------------------------
    def _build_plan(self, bom_rows, op_rows, errors, created_products):
        Product = self.env["product.product"]
        Workcenter = self.env["mrp.workcenter"]
        Uom = self.env["uom.uom"]
        products = {}

        by_name = {}
        for rec in Product.with_context(active_test=False).search([]):
            by_name.setdefault(_norm_name(rec.name), rec)

        def find_uom(name, sheet, row_no, ref=None):
            """Satuan dari file. Bila `ref` (satuan produk) diberikan, pilih yang sebanding dengannya."""
            if not name:
                return None
            # Nama persis dari file diutamakan ('pcs' tetap 'pcs'); alias hanya cadangan (mis. 'gr' -> 'g').
            for alias in [name] + [a for a in UOM_ALIASES.get(name.lower(), []) if a.lower() != name.lower()]:
                found = Uom.search([("name", "=ilike", alias)], limit=1)
                if found:
                    return found
            errors.append(f"Sheet {sheet} baris {row_no}: satuan '{name}' tidak ditemukan.")
            return False

        def find_product(code, name, sheet, row_no, uom_name=""):
            """Cari lewat kode; tanpa kode, lewat nama (dicocokkan longgar, dibuat bila belum ada)."""
            if code:
                if code not in products:
                    found = Product.search([("default_code", "=", code)], limit=2)
                    if not found:
                        errors.append(f"Sheet {sheet} baris {row_no}: produk dengan kode '{code}' tidak ditemukan.")
                        products[code] = False
                    elif len(found) > 1:
                        errors.append(f"Sheet {sheet} baris {row_no}: kode '{code}' dipakai lebih dari satu produk.")
                        products[code] = False
                    else:
                        products[code] = found
                return products[code]
            key = _norm_name(name)
            if not key:
                errors.append(f"Sheet {sheet} baris {row_no}: nama produk kosong.")
                return False
            if key not in by_name:
                uom = find_uom(uom_name, sheet, row_no)
                if uom is False:
                    return False
                values = {"name": name.strip(), "type": "consu"}
                if "is_storable" in Product._fields:
                    values["is_storable"] = True
                if uom:
                    values["uom_id"] = uom.id
                by_name[key] = Product.create(values)
                created_products.append(by_name[key].display_name)
            return by_name[key]

        def number(value, label, sheet, row_no):
            try:
                return bom_excel.to_number(value)
            except ValueError:
                errors.append(f"Sheet {sheet} baris {row_no}: {label} '{value}' bukan angka.")
                return None

        groups = OrderedDict()
        for row in bom_rows:
            row_no = row["_row"]
            product_code = bom_excel.to_text(row.get("product_code"))
            product_name = bom_excel.to_text(row.get("product_name"))
            sheet_name = row.get("_sheet", "BoM")
            if not product_code and not product_name:
                errors.append(f"Sheet {sheet_name} baris {row_no}: Kode Produk Jadi kosong.")
                continue
            bom_code = bom_excel.to_text(row.get("bom_code"))
            key = (product_code or _norm_name(product_name), bom_code)
            group = groups.get(key)
            if group is None:
                finished = find_product(
                    product_code, product_name, sheet_name, row_no, bom_excel.to_text(row.get("product_uom")))
                if not finished:
                    continue
                qty = number(row.get("product_qty"), "Qty Produk Jadi", "BoM", row_no)
                bom_type = BOM_TYPES.get(bom_excel.to_text(row.get("bom_type")).lower())
                if not bom_type:
                    errors.append(f"Sheet BoM baris {row_no}: Tipe BoM harus 'normal' atau 'kit'.")
                group = groups[key] = {
                    "product": finished,
                    "code": bom_code,
                    "qty": qty or 1.0,
                    "type": bom_type or "normal",
                    "brand": bom_excel.to_text(row.get("brand")),
                    "variant": bom_excel.to_text(row.get("variant")),
                    "uom": find_uom(bom_excel.to_text(row.get("product_uom")), sheet_name, row_no),
                    "jenis_produk": bom_excel.to_text(row.get("jenis_produk")),
                    "jenis_kemasan": bom_excel.to_text(row.get("jenis_kemasan")),
                    "components": [],
                    "operations": [],
                }
            comp_code = bom_excel.to_text(row.get("comp_code"))
            comp_name = bom_excel.to_text(row.get("comp_name")) if not comp_code else ""
            comp_qty_raw = row.get("comp_qty")
            if not comp_code and not comp_name and bom_excel.to_text(comp_qty_raw) == "":
                continue  # baris hanya mendefinisikan BoM tanpa komponen
            if not comp_code and not comp_name:
                errors.append(f"Sheet {sheet_name} baris {row_no}: Kode Komponen kosong.")
                continue
            component = find_product(
                comp_code, comp_name, sheet_name, row_no, bom_excel.to_text(row.get("comp_uom")))
            comp_qty = number(comp_qty_raw, "Qty Komponen", "BoM", row_no)
            if comp_qty is None:
                if bom_excel.to_text(comp_qty_raw) != "":
                    continue  # bukan angka, sudah dicatat sebagai error
                comp_qty = 0.0  # qty kosong diimpor apa adanya sebagai 0
            if not component:
                continue
            uom_name = bom_excel.to_text(row.get("comp_uom"))
            uom = component.uom_id
            if uom_name:
                uom = find_uom(uom_name, sheet_name, row_no)
                if not uom:
                    continue
            group["components"].append({"product": component, "qty": comp_qty, "uom": uom})

        for row in op_rows:
            row_no = row["_row"]
            product_code = bom_excel.to_text(row.get("product_code"))
            bom_code = bom_excel.to_text(row.get("bom_code"))
            name = bom_excel.to_text(row.get("name"))
            wc_name = bom_excel.to_text(row.get("workcenter"))
            if not product_code or not name or not wc_name:
                errors.append(f"Sheet Operations baris {row_no}: Kode Produk Jadi, Operation, dan Work Center wajib diisi.")
                continue
            candidates = [g for (pcode, _bcode), g in groups.items() if pcode == product_code]
            if bom_code:
                candidates = [g for g in candidates if g["code"] == bom_code]
            if not candidates:
                errors.append(
                    f"Sheet Operations baris {row_no}: produk '{product_code}'"
                    f"{' / BoM ' + bom_code if bom_code else ''} tidak ada di sheet BoM."
                )
                continue
            if len(candidates) > 1:
                errors.append(
                    f"Sheet Operations baris {row_no}: produk '{product_code}' punya lebih dari satu BoM, "
                    f"isi kolom Referensi BoM."
                )
                continue
            workcenters = Workcenter.search([
                ("name", "=ilike", wc_name),
                ("company_id", "in", [False, self.env.company.id]),
            ])
            if not workcenters:
                errors.append(f"Sheet Operations baris {row_no}: work center '{wc_name}' tidak ditemukan.")
                continue
            if len(workcenters) > 1:
                errors.append(f"Sheet Operations baris {row_no}: work center '{wc_name}' ada lebih dari satu.")
                continue
            duration = number(row.get("duration"), "Durasi", "Operations", row_no)
            sequence = number(row.get("sequence"), "Urutan", "Operations", row_no)
            candidates[0]["operations"].append({
                "name": name,
                "workcenter": workcenters,
                "duration": 60.0 if duration is None else duration,
                "sequence": sequence,
            })
        return groups

    # ------------------------------------------------------------------
    # Tahap 2: simpan
    # ------------------------------------------------------------------
    def _existing_bom(self, group):
        domain = [
            ("product_tmpl_id", "=", group["product"].product_tmpl_id.id),
            ("company_id", "in", [False, self.env.company.id]),
        ]
        BoM = self.env["mrp.bom"]
        if group["code"]:
            found = BoM.search(domain + [("code", "=", group["code"])], limit=1)
            if found:
                return found
            # BoM lama produk ini yang belum punya Reference dianggap BoM yang sama (bukan dibuat dobel).
            return BoM.search(domain + [("code", "in", [False, ""])], order="id", limit=1)
        return BoM.search(domain, order="id", limit=1)

    def _line_vals(self, items):
        return [
            Command.create({
                "product_id": item["product"].id,
                "product_qty": item["qty"],
                "product_uom_id": item["uom"].id,
                "sequence": (index + 1) * 10,
            })
            for index, item in enumerate(items)
        ]

    def _operation_vals(self, operations):
        return [
            Command.create({
                "name": op["name"],
                "workcenter_id": op["workcenter"].id,
                "time_cycle_manual": op["duration"],
                "sequence": int(op["sequence"]) if op["sequence"] is not None else (index + 1) * 10,
            })
            for index, op in enumerate(operations)
        ]

    def _apply_uoms(self, group):
        """Samakan satuan produk dengan file (satuan lama dianggap salah), sebelum BoM dibuat/diubah."""
        def apply(product, uom):
            """True bila satuan produk sama dengan file. Produk yang sudah dipakai tidak bisa diganti satuannya."""
            if not uom or product.uom_id == uom:
                return True
            try:
                with self.env.cr.savepoint():
                    product.write({"uom_id": uom.id})
                return True
            except UserError:
                return False  # sudah ada transaksi dengan satuan lain; satuan produk dibiarkan

        if not apply(group["product"], group.get("uom")):
            if not group["uom"]._has_common_reference(group["product"].uom_id):
                group["uom"] = group["product"].uom_id
        for item in group["components"]:
            if not apply(item["product"], item["uom"]):
                if not item["uom"]._has_common_reference(item["product"].uom_id):
                    item["uom"] = item["product"].uom_id

    def _category_vals(self, group, cache):
        """Jenis Produk / Jenis Kemasan: cocokkan longgar dengan data yang ada, buat bila belum ada."""
        values = {}
        for field, model, key in (
            ("jenis_produk_id", "mrp.bom.jenis.produk", "jenis_produk"),
            ("jenis_kemasan_id", "mrp.bom.jenis.kemasan", "jenis_kemasan"),
        ):
            name = group.get(key)
            if not name:
                continue
            if (model, _norm_name(name)) not in cache:
                for rec in self.env[model].search([]):
                    cache.setdefault((model, _norm_name(rec.name)), rec)
            if (model, _norm_name(name)) not in cache:
                cache[(model, _norm_name(name))] = self.env[model].create({"name": " ".join(name.split())})
            values[field] = cache[(model, _norm_name(name))].id
        return values

    def _update_bom(self, bom, group, category_vals=None):
        values = {"product_qty": group["qty"], "type": group["type"], **(category_vals or {})}
        if group["code"] and not bom.code:
            values["code"] = group["code"]
        if group.get("uom"):
            values["product_uom_id"] = group["uom"].id
        if group["brand"]:
            values["brand"] = group["brand"]
        if group["variant"]:
            values["product_variant"] = group["variant"]
        bom.write(values)
        for item in group["components"]:
            line = bom.bom_line_ids.filtered(lambda l: l.product_id == item["product"])[:1]
            if line:
                line.write({"product_qty": item["qty"], "product_uom_id": item["uom"].id})
            else:
                bom.write({"bom_line_ids": self._line_vals([item])})
        for index, op in enumerate(group["operations"]):
            existing = bom.operation_ids.filtered(lambda o: (o.name or "").lower() == op["name"].lower())[:1]
            if existing:
                values = {"workcenter_id": op["workcenter"].id, "time_cycle_manual": op["duration"]}
                if op["sequence"] is not None:
                    values["sequence"] = int(op["sequence"])
                existing.write(values)
            else:
                bom.write({"operation_ids": self._operation_vals([op])})

    def _load_rows(self):
        self.ensure_one()
        if not self.file:
            raise UserError("Pilih file Excel (.xlsx) dulu. Belum punya formatnya? Klik Download Format.")
        try:
            bom_rows, op_rows = bom_excel.parse_workbook(base64.b64decode(self.file))
        except ValueError as error:
            raise UserError(str(error)) from error
        except Exception as error:  # noqa: BLE001 - file rusak / bukan xlsx
            raise UserError("File tidak bisa dibaca. Pastikan file berformat .xlsx sesuai Format Import.") from error
        if not bom_rows:
            raise UserError("Sheet BoM tidak berisi data.")
        return bom_rows, op_rows

    @staticmethod
    def _row_key(row):
        product_code = bom_excel.to_text(row.get("product_code"))
        product_name = bom_excel.to_text(row.get("product_name"))
        if not product_code and not product_name:
            return None
        return (product_code or _norm_name(product_name), bom_excel.to_text(row.get("bom_code")))

    def _group_keys(self, bom_rows):
        keys = []
        for row in bom_rows:
            key = self._row_key(row)
            if key and key not in keys:
                keys.append(key)
        return keys

    def action_import(self):
        """Tahap 1: periksa semua baris (tanpa menyimpan apa pun), lalu buka layar progres."""
        self.ensure_one()
        bom_rows, op_rows = self._load_rows()
        errors = []
        try:
            with self.env.cr.savepoint():
                self._build_plan(bom_rows, op_rows, errors, [])
                raise _DryRun()
        except _DryRun:
            pass
        self.env.invalidate_all()
        if errors:
            shown = errors[:40]
            more = f"\n... dan {len(errors) - 40} kesalahan lain." if len(errors) > 40 else ""
            raise UserError(
                "Import dibatalkan, belum ada BoM yang tersimpan. Perbaiki baris berikut lalu coba lagi:\n\n"
                + "\n".join(shown) + more
            )
        return {
            "type": "ir.actions.client",
            "tag": "custom_bom.import_progress",
            "name": "Import BoM",
            "target": "new",
            "params": {
                "wizard_id": self.id,
                "total": len(self._group_keys(bom_rows)),
                "chunk": IMPORT_CHUNK,
            },
        }

    def import_chunk(self, start, size):
        """Tahap 2: simpan satu bagian (size BoM mulai dari urutan start). Dipanggil berulang oleh layar progres."""
        self.ensure_one()
        bom_rows, op_rows = self._load_rows()
        keys = self._group_keys(bom_rows)[start:start + size]
        key_set = set(keys)
        chunk_rows = [row for row in bom_rows if self._row_key(row) in key_set]
        chunk_ops = []
        for row in op_rows:
            code = bom_excel.to_text(row.get("product_code"))
            bom_code = bom_excel.to_text(row.get("bom_code"))
            if any(k[0] == code and (not bom_code or k[1] == bom_code) for k in keys):
                chunk_ops.append(row)

        errors = []
        created_products = []
        groups = self._build_plan(chunk_rows, chunk_ops, errors, created_products)
        if errors:
            raise UserError("\n".join(errors[:40]))

        created = updated = skipped = 0
        category_cache = {}
        for group in groups.values():
            existing = self._existing_bom(group)
            if existing and self.mode == "skip":
                skipped += 1
                continue
            self._apply_uoms(group)
            category_vals = self._category_vals(group, category_cache)
            if existing:
                self._update_bom(existing, group, category_vals)
                updated += 1
                continue
            self.env["mrp.bom"].create({
                "product_tmpl_id": group["product"].product_tmpl_id.id,
                "product_qty": group["qty"],
                "product_uom_id": group["product"].uom_id.id,
                "code": group["code"] or False,
                "type": group["type"],
                "brand": group["brand"] or False,
                "product_variant": group["variant"] or False,
                **category_vals,
                "company_id": self.env.company.id,
                "bom_line_ids": self._line_vals(group["components"]),
                "operation_ids": self._operation_vals(group["operations"]),
            })
            created += 1
        return {
            "processed": len(keys),
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "new_products": len(created_products),
        }
