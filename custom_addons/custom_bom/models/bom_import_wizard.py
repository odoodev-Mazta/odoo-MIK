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
}


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
    def _build_plan(self, bom_rows, op_rows, errors):
        Product = self.env["product.product"]
        Workcenter = self.env["mrp.workcenter"]
        Uom = self.env["uom.uom"]
        products = {}

        def find_product(code, sheet, row_no):
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
            if not product_code:
                errors.append(f"Sheet BoM baris {row_no}: Kode Produk Jadi kosong.")
                continue
            bom_code = bom_excel.to_text(row.get("bom_code"))
            key = (product_code, bom_code)
            group = groups.get(key)
            if group is None:
                finished = find_product(product_code, "BoM", row_no)
                if not finished:
                    continue
                qty = number(row.get("product_qty"), "Qty Produk Jadi", "BoM", row_no)
                if qty is not None and qty <= 0:
                    errors.append(f"Sheet BoM baris {row_no}: Qty Produk Jadi harus lebih dari 0.")
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
                    "components": [],
                    "operations": [],
                }
            comp_code = bom_excel.to_text(row.get("comp_code"))
            comp_qty_raw = row.get("comp_qty")
            if not comp_code and bom_excel.to_text(comp_qty_raw) == "":
                continue  # baris hanya mendefinisikan BoM tanpa komponen
            if not comp_code:
                errors.append(f"Sheet BoM baris {row_no}: Kode Komponen kosong.")
                continue
            component = find_product(comp_code, "BoM", row_no)
            comp_qty = number(comp_qty_raw, "Qty Komponen", "BoM", row_no)
            if comp_qty is None or comp_qty <= 0:
                if comp_qty is None and bom_excel.to_text(comp_qty_raw) == "":
                    errors.append(f"Sheet BoM baris {row_no}: Qty Komponen kosong.")
                elif comp_qty is not None:
                    errors.append(f"Sheet BoM baris {row_no}: Qty Komponen harus lebih dari 0.")
                continue
            if not component:
                continue
            uom_name = bom_excel.to_text(row.get("comp_uom"))
            uom = component.uom_id
            if uom_name:
                uoms = Uom.search([("name", "=ilike", uom_name)], limit=2)
                if not uoms:
                    errors.append(f"Sheet BoM baris {row_no}: satuan '{uom_name}' tidak ditemukan.")
                    continue
                uom = uoms[0]
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
        if group["code"]:
            domain.append(("code", "=", group["code"]))
        return self.env["mrp.bom"].search(domain, limit=1)

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

    def _update_bom(self, bom, group):
        values = {"product_qty": group["qty"], "type": group["type"]}
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

    def action_import(self):
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

        errors = []
        groups = self._build_plan(bom_rows, op_rows, errors)
        if errors:
            shown = errors[:40]
            more = f"\n... dan {len(errors) - 40} kesalahan lain." if len(errors) > 40 else ""
            raise UserError(
                "Import dibatalkan, belum ada BoM yang tersimpan. Perbaiki baris berikut lalu coba lagi:\n\n"
                + "\n".join(shown) + more
            )

        created = updated = skipped = 0
        for group in groups.values():
            existing = self._existing_bom(group)
            if existing and self.mode == "skip":
                skipped += 1
                continue
            if existing:
                self._update_bom(existing, group)
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
                "company_id": self.env.company.id,
                "bom_line_ids": self._line_vals(group["components"]),
                "operation_ids": self._operation_vals(group["operations"]),
            })
            created += 1

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Import BoM selesai",
                "message": f"Dibuat: {created} · Diperbarui: {updated} · Dilewati (sudah ada): {skipped}",
                "type": "success",
                "sticky": True,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }
