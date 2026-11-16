import base64
from collections import OrderedDict
from datetime import datetime, time

from odoo import Command, fields, models
from odoo.exceptions import UserError

from . import excel_io

SHEET = "Sales Order"

# Satu baris = satu baris produk di SO; data header diulang di tiap baris.
SO_COLUMNS = [
    ("name", "No. SO*", 18),
    ("date", "Tanggal Order", 15),
    ("customer", "Customer*", 30),
    ("mou", "No. MOU", 22),
    ("brand", "Nama Brand", 20),
    ("repeat", "Repeat Order", 14),
    ("ref", "Ref. Customer", 20),
    ("product_code", "Kode Produk*", 18),
    ("description", "Deskripsi", 34),
    ("qty", "Qty*", 12),
    ("uom", "Satuan", 12),
    ("price", "Harga Satuan", 16),
    ("discount", "Diskon (%)", 12),
    ("tax", "Pajak", 18),
]
SO_EXPORT_COLUMNS = SO_COLUMNS + [("state", "Status (info)", 16)]

HELP_LINES = [
    "PETUNJUK IMPORT SALES ORDER",
    "",
    "Satu baris = satu baris produk. Data header (No. SO, customer, dst.) diulang di tiap baris;",
    "yang dipakai adalah baris pertama untuk setiap No. SO.",
    "",
    "  - No. SO*        : nomor SO. Dipakai sebagai nomor SO di Odoo dan harus unik.",
    "  - Tanggal Order  : YYYY-MM-DD atau DD/MM/YYYY. Kosong = hari ini.",
    "  - Customer*      : nama customer persis seperti di Odoo (harus sudah ada).",
    "  - No. MOU        : Kode MOU (opsional). Harus milik customer yang sama.",
    "  - Repeat Order   : Ya / Tidak. Kosong = Tidak.",
    "  - Kode Produk*   : Internal Reference produk (harus sudah ada).",
    "  - Qty*           : jumlah, harus lebih dari 0.",
    "  - Satuan         : nama satuan. Kosong = satuan bawaan produk.",
    "  - Harga Satuan   : kosong = harga otomatis dari Odoo.",
    "  - Pajak          : nama pajak penjualan; beberapa pajak dipisah titik koma (;).",
    "                     Kosong = pajak bawaan produk.",
    "",
    "Aturan",
    "  - SO dibuat sebagai Quotation (belum dikonfirmasi).",
    "  - SO dengan No. SO yang sudah ada dilewati, tidak ditimpa.",
    "  - Semua baris diperiksa dulu. Jika ada satu saja yang salah, tidak ada yang diimpor.",
    "  - Baris contoh hanya contoh: hapus atau ganti dengan data asli.",
    "  - Export SO menghasilkan file dengan format yang sama (kolom Status hanya informasi).",
]

SAMPLE_ROWS = [
    {"name": "SO-CONTOH-001", "date": "2026-11-16", "customer": "Nama Customer", "mou": "",
     "brand": "", "repeat": "Tidak", "ref": "", "product_code": "MZM-003",
     "description": "", "qty": 100, "uom": "Unit", "price": 25000, "discount": 0, "tax": ""},
    {"name": "SO-CONTOH-001", "date": "2026-11-16", "customer": "Nama Customer", "mou": "",
     "brand": "", "repeat": "Tidak", "ref": "", "product_code": "MZM-004",
     "description": "", "qty": 50, "uom": "Unit", "price": 30000, "discount": 5, "tax": ""},
]


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_import_so(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Import Sales Order",
            "res_model": "sale.order.import.wizard",
            "view_mode": "form",
            "target": "new",
        }

    def action_download_so_format(self):
        content = excel_io.build_workbook([(SHEET, SO_COLUMNS, SAMPLE_ROWS)], help_lines=HELP_LINES)
        return excel_io.download_action(self.env, "format_import_so.xlsx", content)

    def action_export_so(self):
        """Export SO yang dipilih di list; tanpa pilihan = semua SO."""
        orders = self or self.search([])
        states = dict(self._fields["state"].selection)
        rows = []
        for order in orders:
            head = {
                "name": order.name,
                "date": order.date_order.date().isoformat() if order.date_order else "",
                "customer": order.partner_id.name,
                "mou": order.mou_id.draft_name or "",
                "brand": order.brand_name or "",
                "repeat": "Ya" if order.is_repeat_order else "Tidak",
                "ref": order.client_order_ref or "",
                "state": states.get(order.state, order.state),
            }
            lines = order.order_line.filtered(lambda l: not l.display_type and l.product_id)
            if not lines:
                rows.append(dict(head))
            for line in lines:
                rows.append({
                    **head,
                    "product_code": line.product_id.default_code or "",
                    "description": line.name or "",
                    "qty": line.product_uom_qty,
                    "uom": line.product_uom_id.name,
                    "price": line.price_unit,
                    "discount": line.discount,
                    "tax": ";".join(line.tax_ids.mapped("name")),
                })
        content = excel_io.build_workbook([(SHEET, SO_EXPORT_COLUMNS, rows)])
        return excel_io.download_action(self.env, "export_so.xlsx", content)


class SaleOrderImportWizard(models.TransientModel):
    _name = "sale.order.import.wizard"
    _description = "Import Sales Order dari Excel"

    file = fields.Binary(string="File Excel (.xlsx)")
    filename = fields.Char()

    def action_download_format(self):
        return self.env["sale.order"].action_download_so_format()

    # ------------------------------------------------------------------
    # Tahap 1: periksa semua baris (belum ada yang disimpan)
    # ------------------------------------------------------------------
    def _build_plan(self, rows, errors):
        Partner = self.env["res.partner"]
        Product = self.env["product.product"]
        Mou = self.env["draft.maklon"]
        Uom = self.env["uom.uom"]
        Tax = self.env["account.tax"]
        company = self.env.company
        partners, products, mous, taxes = {}, {}, {}, {}

        def number(value, label, row_no):
            try:
                return excel_io.to_number(value)
            except ValueError:
                errors.append(f"Baris {row_no}: {label} '{value}' bukan angka.")
                return None

        def find_partner(name, row_no):
            if name not in partners:
                found = Partner.search([("name", "=ilike", name)], limit=2)
                if not found:
                    errors.append(f"Baris {row_no}: customer '{name}' tidak ditemukan.")
                    partners[name] = False
                elif len(found) > 1:
                    errors.append(f"Baris {row_no}: nama customer '{name}' ada lebih dari satu di Odoo.")
                    partners[name] = False
                else:
                    partners[name] = found
            return partners[name]

        def find_product(code, row_no):
            if code not in products:
                found = Product.search([("default_code", "=", code)], limit=2)
                if not found:
                    errors.append(f"Baris {row_no}: produk dengan kode '{code}' tidak ditemukan.")
                    products[code] = False
                elif len(found) > 1:
                    errors.append(f"Baris {row_no}: kode produk '{code}' dipakai lebih dari satu produk.")
                    products[code] = False
                else:
                    products[code] = found
            return products[code]

        def find_taxes(text, row_no):
            result = Tax
            for name in [part.strip() for part in text.replace(",", ";").split(";") if part.strip()]:
                if name not in taxes:
                    found = Tax.search([
                        ("name", "=ilike", name), ("type_tax_use", "=", "sale"),
                        ("company_id", "=", company.id),
                    ], limit=1)
                    if not found:
                        errors.append(f"Baris {row_no}: pajak penjualan '{name}' tidak ditemukan.")
                    taxes[name] = found
                result |= taxes[name]
            return result

        groups = OrderedDict()
        for row in rows:
            row_no = row["_row"]
            name = excel_io.to_text(row.get("name"))
            if not name:
                errors.append(f"Baris {row_no}: No. SO kosong.")
                continue
            group = groups.get(name)
            if group is None:
                customer_name = excel_io.to_text(row.get("customer"))
                if not customer_name:
                    errors.append(f"Baris {row_no}: Customer kosong.")
                    continue
                partner = find_partner(customer_name, row_no)
                if not partner:
                    continue
                mou = False
                mou_code = excel_io.to_text(row.get("mou"))
                if mou_code:
                    if mou_code not in mous:
                        mous[mou_code] = Mou.search([("draft_name", "=", mou_code)], limit=1)
                    mou = mous[mou_code]
                    if not mou:
                        errors.append(f"Baris {row_no}: MOU '{mou_code}' tidak ditemukan.")
                        continue
                    if mou.nama_cust != partner:
                        errors.append(f"Baris {row_no}: MOU '{mou_code}' bukan milik customer '{customer_name}'.")
                        continue
                try:
                    order_date = excel_io.to_date(row.get("date"))
                except ValueError as error:
                    errors.append(f"Baris {row_no}: Tanggal Order '{error}' tidak valid (pakai YYYY-MM-DD).")
                    order_date = None
                repeat = excel_io.to_text(row.get("repeat")).lower()
                if repeat not in ("", "ya", "tidak", "yes", "no", "true", "false", "1", "0"):
                    errors.append(f"Baris {row_no}: Repeat Order harus 'Ya' atau 'Tidak'.")
                group = groups[name] = {
                    "partner": partner,
                    "mou": mou,
                    "date": order_date,
                    "brand": excel_io.to_text(row.get("brand")),
                    "repeat": repeat in ("ya", "yes", "true", "1"),
                    "ref": excel_io.to_text(row.get("ref")),
                    "lines": [],
                }

            code = excel_io.to_text(row.get("product_code"))
            qty_raw = row.get("qty")
            if not code and excel_io.to_text(qty_raw) == "":
                continue  # baris hanya mendefinisikan SO tanpa produk
            if not code:
                errors.append(f"Baris {row_no}: Kode Produk kosong.")
                continue
            product = find_product(code, row_no)
            qty = number(qty_raw, "Qty", row_no)
            if qty is None:
                if excel_io.to_text(qty_raw) == "":
                    errors.append(f"Baris {row_no}: Qty kosong.")
                continue
            if qty <= 0:
                errors.append(f"Baris {row_no}: Qty harus lebih dari 0.")
                continue
            price = number(row.get("price"), "Harga Satuan", row_no)
            discount = number(row.get("discount"), "Diskon", row_no)
            uom = product.uom_id if product else Uom
            uom_name = excel_io.to_text(row.get("uom"))
            if uom_name:
                found = Uom.search([("name", "=ilike", uom_name)], limit=1)
                if not found:
                    errors.append(f"Baris {row_no}: satuan '{uom_name}' tidak ditemukan.")
                    continue
                uom = found
            line_taxes = find_taxes(excel_io.to_text(row.get("tax")), row_no)
            if not product:
                continue
            group["lines"].append({
                "product": product,
                "description": excel_io.to_text(row.get("description")),
                "qty": qty,
                "uom": uom,
                "price": price,
                "discount": discount,
                "taxes": line_taxes,
            })
        return groups

    # ------------------------------------------------------------------
    # Tahap 2: simpan
    # ------------------------------------------------------------------
    def _order_vals(self, name, group):
        vals = {
            "name": name,
            "partner_id": group["partner"].id,
            "company_id": self.env.company.id,
            "is_repeat_order": group["repeat"],
        }
        if group["date"]:
            vals["date_order"] = datetime.combine(group["date"], time(8, 0))
        if group["mou"]:
            vals["mou_id"] = group["mou"].id
        if group["brand"]:
            vals["brand_name"] = group["brand"]
        if group["ref"]:
            vals["client_order_ref"] = group["ref"]
        lines = []
        for item in group["lines"]:
            line = {
                "product_id": item["product"].id,
                "product_uom_qty": item["qty"],
                "product_uom_id": item["uom"].id,
            }
            if item["description"]:
                line["name"] = item["description"]
            if item["price"] is not None:
                line["price_unit"] = item["price"]
            if item["discount"] is not None:
                line["discount"] = item["discount"]
            if item["taxes"]:
                line["tax_ids"] = [Command.set(item["taxes"].ids)]
            lines.append(Command.create(line))
        vals["order_line"] = lines
        return vals

    def action_import(self):
        self.ensure_one()
        if not self.file:
            raise UserError("Pilih file Excel (.xlsx) dulu. Belum punya formatnya? Klik Download Format.")
        try:
            workbook = excel_io.load(base64.b64decode(self.file))
            rows = excel_io.parse_sheet(workbook, SHEET, SO_COLUMNS)
        except ValueError as error:
            raise UserError(str(error)) from error
        except Exception as error:  # noqa: BLE001 - file rusak / bukan xlsx
            raise UserError("File tidak bisa dibaca. Pastikan file berformat .xlsx sesuai Format Import.") from error
        if not rows:
            raise UserError("Sheet tidak berisi data.")

        errors = []
        groups = self._build_plan(rows, errors)
        if errors:
            shown = errors[:40]
            more = f"\n... dan {len(errors) - 40} kesalahan lain." if len(errors) > 40 else ""
            raise UserError(
                "Import dibatalkan, belum ada SO yang tersimpan. Perbaiki baris berikut lalu coba lagi:\n\n"
                + "\n".join(shown) + more
            )

        Order = self.env["sale.order"]
        created = skipped = 0
        for name, group in groups.items():
            if Order.search_count([("name", "=", name), ("company_id", "=", self.env.company.id)]):
                skipped += 1
                continue
            Order.create(self._order_vals(name, group))
            created += 1
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Import Sales Order selesai",
                "message": f"Dibuat: {created} · Dilewati (No. SO sudah ada): {skipped}",
                "type": "success",
                "sticky": True,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }
