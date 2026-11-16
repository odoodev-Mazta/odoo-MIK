import base64
from collections import OrderedDict
from datetime import datetime, time

from odoo import Command, fields, models
from odoo.exceptions import UserError

from odoo.addons.custom_mou.models import excel_io

SHEET = "Delivery"

# Satu baris = satu produk di Delivery; data header diulang di tiap baris.
PICKING_COLUMNS = [
    ("name", "No. Delivery", 20),
    ("customer", "Customer*", 30),
    ("mou", "No. MOU", 22),
    ("origin", "Source Document", 20),
    ("date", "Tanggal Jadwal", 16),
    ("product_code", "Kode Produk*", 18),
    ("qty", "Qty*", 12),
    ("uom", "Satuan", 12),
    ("date_estimasi", "Tanggal Estimasi", 16),
    ("jenis", "Jenis Produk", 14),
    ("kemasan", "Kemasan", 14),
    ("ukuran", "Ukuran", 14),
    ("hna", "HNA", 14),
    ("discount", "Diskon (%)", 12),
]
PICKING_EXPORT_COLUMNS = PICKING_COLUMNS + [("state", "Status (info)", 16)]

JENIS = {"lokal": "lokal", "import": "import"}
KEMASAN = {
    "jar": "jar", "tube": "tube", "sachet": "sachet", "botol": "botol",
    "pump": "pump", "tube pump": "pump",
}

HELP_LINES = [
    "PETUNJUK IMPORT DELIVERY",
    "",
    "Satu baris = satu produk. Data header diulang di tiap baris. Baris dengan No. Delivery,",
    "Customer, Source Document, dan Tanggal Jadwal yang sama digabung menjadi satu Delivery.",
    "",
    "  - No. Delivery    : opsional. Kosong = nomor otomatis. Bila diisi dan sudah ada, Delivery dilewati.",
    "  - Customer*       : nama customer persis seperti di Odoo (harus sudah ada).",
    "  - No. MOU         : Kode MOU (opsional). Harus milik customer yang sama.",
    "  - Source Document : mis. nomor SO (hanya teks referensi).",
    "  - Tanggal Jadwal  : YYYY-MM-DD atau DD/MM/YYYY. Kosong = sekarang.",
    "  - Kode Produk*    : Internal Reference produk (harus sudah ada).",
    "  - Qty*            : jumlah, harus lebih dari 0.",
    "  - Satuan          : nama satuan. Kosong = satuan bawaan produk.",
    "  - Jenis Produk    : lokal / import.",
    "  - Kemasan         : jar / tube / sachet / botol / pump.",
    "",
    "Aturan",
    "  - Delivery dibuat dengan status Draft memakai tipe operasi Delivery Orders milik perusahaan aktif.",
    "  - Semua baris diperiksa dulu. Jika ada satu saja yang salah, tidak ada yang diimpor.",
    "  - Baris contoh hanya contoh: hapus atau ganti dengan data asli.",
    "  - Export Delivery menghasilkan file dengan format yang sama (kolom Status hanya informasi).",
]

SAMPLE_ROWS = [
    {"name": "", "customer": "Nama Customer", "mou": "", "origin": "SO-CONTOH-001",
     "date": "2026-11-20", "product_code": "MZM-003", "qty": 100, "uom": "Unit",
     "date_estimasi": "", "jenis": "lokal", "kemasan": "jar", "ukuran": "50 ml", "hna": 25000, "discount": 0},
    {"name": "", "customer": "Nama Customer", "mou": "", "origin": "SO-CONTOH-001",
     "date": "2026-11-20", "product_code": "MZM-004", "qty": 50, "uom": "Unit",
     "date_estimasi": "", "jenis": "import", "kemasan": "tube", "ukuran": "30 ml", "hna": 30000, "discount": 5},
]


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def action_import_picking(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Import Delivery",
            "res_model": "stock.picking.import.wizard",
            "view_mode": "form",
            "target": "new",
        }

    def action_download_picking_format(self):
        content = excel_io.build_workbook([(SHEET, PICKING_COLUMNS, SAMPLE_ROWS)], help_lines=HELP_LINES)
        return excel_io.download_action(self.env, "format_import_delivery.xlsx", content)

    def action_export_picking(self):
        """Export Delivery yang dipilih di list; tanpa pilihan = semua Delivery Orders."""
        pickings = self or self.search([("picking_type_code", "=", "outgoing")])
        states = dict(self._fields["state"].selection)
        label = {
            "kemasan": dict(self.env["stock.move"]._fields["kemasan"].selection),
            "jenis": dict(self.env["stock.move"]._fields["jenis_product"].selection),
        }
        rows = []
        for picking in pickings:
            head = {
                "name": picking.name,
                "customer": picking.partner_id.name or "",
                "mou": picking.mou_id.draft_name or "",
                "origin": picking.origin or "",
                "date": picking.scheduled_date.date().isoformat() if picking.scheduled_date else "",
                "state": states.get(picking.state, picking.state),
            }
            moves = picking.move_ids.filtered(lambda m: m.product_id)
            if not moves:
                rows.append(dict(head))
            for move in moves:
                rows.append({
                    **head,
                    "product_code": move.product_id.default_code or "",
                    "qty": move.product_uom_qty,
                    "uom": move.product_uom.name,
                    "date_estimasi": move.date_estimasi.isoformat() if move.date_estimasi else "",
                    "jenis": move.jenis_product or "",
                    "kemasan": move.kemasan or "",
                    "ukuran": move.ukuran or "",
                    "hna": move.product_hna,
                    "discount": move.diskon,
                })
        content = excel_io.build_workbook([(SHEET, PICKING_EXPORT_COLUMNS, rows)])
        return excel_io.download_action(self.env, "export_delivery.xlsx", content)


class StockPickingImportWizard(models.TransientModel):
    _name = "stock.picking.import.wizard"
    _description = "Import Delivery dari Excel"

    file = fields.Binary(string="File Excel (.xlsx)")
    filename = fields.Char()

    def action_download_format(self):
        return self.env["stock.picking"].action_download_picking_format()

    # ------------------------------------------------------------------
    # Tahap 1: periksa semua baris (belum ada yang disimpan)
    # ------------------------------------------------------------------
    def _build_plan(self, rows, errors):
        Partner = self.env["res.partner"]
        Product = self.env["product.product"]
        Mou = self.env["draft.maklon"]
        Uom = self.env["uom.uom"]
        partners, products, mous = {}, {}, {}

        def number(value, label, row_no):
            try:
                return excel_io.to_number(value)
            except ValueError:
                errors.append(f"Baris {row_no}: {label} '{value}' bukan angka.")
                return None

        def date_value(value, label, row_no):
            try:
                return excel_io.to_date(value)
            except ValueError as error:
                errors.append(f"Baris {row_no}: {label} '{error}' tidak valid (pakai YYYY-MM-DD).")
                return None

        def choice(value, mapping, label, row_no):
            text = excel_io.to_text(value).lower()
            if not text:
                return False
            if text not in mapping:
                errors.append(f"Baris {row_no}: {label} '{value}' harus salah satu dari: {', '.join(sorted(set(mapping.values())))}.")
                return False
            return mapping[text]

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

        groups = OrderedDict()
        for row in rows:
            row_no = row["_row"]
            customer_name = excel_io.to_text(row.get("customer"))
            if not customer_name:
                errors.append(f"Baris {row_no}: Customer kosong.")
                continue
            partner = find_partner(customer_name, row_no)
            if not partner:
                continue
            name = excel_io.to_text(row.get("name"))
            origin = excel_io.to_text(row.get("origin"))
            scheduled = date_value(row.get("date"), "Tanggal Jadwal", row_no)
            key = (name, customer_name.lower(), origin, scheduled)
            group = groups.get(key)
            if group is None:
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
                group = groups[key] = {
                    "name": name, "partner": partner, "mou": mou, "origin": origin,
                    "scheduled": scheduled, "moves": [],
                }

            code = excel_io.to_text(row.get("product_code"))
            qty_raw = row.get("qty")
            if not code and excel_io.to_text(qty_raw) == "":
                continue  # baris hanya mendefinisikan Delivery tanpa produk
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
            uom = product.uom_id if product else Uom
            uom_name = excel_io.to_text(row.get("uom"))
            if uom_name:
                found = Uom.search([("name", "=ilike", uom_name)], limit=1)
                if not found:
                    errors.append(f"Baris {row_no}: satuan '{uom_name}' tidak ditemukan.")
                    continue
                uom = found
            move = {
                "product": product,
                "qty": qty,
                "uom": uom,
                "date_estimasi": date_value(row.get("date_estimasi"), "Tanggal Estimasi", row_no),
                "jenis": choice(row.get("jenis"), JENIS, "Jenis Produk", row_no),
                "kemasan": choice(row.get("kemasan"), KEMASAN, "Kemasan", row_no),
                "ukuran": excel_io.to_text(row.get("ukuran")),
                "hna": number(row.get("hna"), "HNA", row_no),
                "discount": number(row.get("discount"), "Diskon", row_no),
            }
            if product:
                group["moves"].append(move)
        return groups

    # ------------------------------------------------------------------
    # Tahap 2: simpan
    # ------------------------------------------------------------------
    def _picking_type(self):
        picking_type = self.env["stock.picking.type"].search([
            ("code", "=", "outgoing"), ("company_id", "=", self.env.company.id),
        ], limit=1)
        if not picking_type:
            raise UserError("Tipe operasi Delivery Orders untuk perusahaan ini tidak ditemukan.")
        return picking_type

    def _picking_vals(self, group, picking_type):
        partner = group["partner"]
        dest = partner.property_stock_customer or picking_type.default_location_dest_id
        moves = []
        for item in group["moves"]:
            move = {
                "product_id": item["product"].id,
                "product_uom_qty": item["qty"],
                "product_uom": item["uom"].id,
                "location_id": picking_type.default_location_src_id.id,
                "location_dest_id": dest.id,
                "date_estimasi": item["date_estimasi"] or False,
                "jenis_product": item["jenis"] or False,
                "kemasan": item["kemasan"] or False,
                "ukuran": item["ukuran"] or False,
                "product_hna": item["hna"] or 0.0,
                "diskon": item["discount"] or 0.0,
            }
            moves.append(Command.create(move))
        vals = {
            "partner_id": partner.id,
            "picking_type_id": picking_type.id,
            "location_id": picking_type.default_location_src_id.id,
            "location_dest_id": dest.id,
            "company_id": self.env.company.id,
            "origin": group["origin"] or False,
            "move_ids": moves,
        }
        if group["name"]:
            vals["name"] = group["name"]
        if group["scheduled"]:
            vals["scheduled_date"] = datetime.combine(group["scheduled"], time(8, 0))
        if group["mou"]:
            vals["mou_id"] = group["mou"].id
        return vals

    def action_import(self):
        self.ensure_one()
        if not self.file:
            raise UserError("Pilih file Excel (.xlsx) dulu. Belum punya formatnya? Klik Download Format.")
        try:
            workbook = excel_io.load(base64.b64decode(self.file))
            rows = excel_io.parse_sheet(workbook, SHEET, PICKING_COLUMNS)
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
                "Import dibatalkan, belum ada Delivery yang tersimpan. Perbaiki baris berikut lalu coba lagi:\n\n"
                + "\n".join(shown) + more
            )

        picking_type = self._picking_type()
        Picking = self.env["stock.picking"]
        created = skipped = 0
        for group in groups.values():
            if group["name"] and Picking.search_count([
                ("name", "=", group["name"]), ("company_id", "=", self.env.company.id),
            ]):
                skipped += 1
                continue
            Picking.create(self._picking_vals(group, picking_type))
            created += 1
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Import Delivery selesai",
                "message": f"Dibuat: {created} · Dilewati (No. Delivery sudah ada): {skipped}",
                "type": "success",
                "sticky": True,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }
