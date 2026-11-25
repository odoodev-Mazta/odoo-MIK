import base64
import io
import re
from datetime import date, datetime

from openpyxl import load_workbook

from odoo import fields, models
from odoo.exceptions import UserError

# Judul kolom di Excel (dinormalkan: huruf besar, tanpa spasi/tanda baca) -> field
HEADER_MAP = {
    "URUTANPRODUKSI": "sequence_label",
    "TGLPO": "po_date",
    "NOPO": "po_number",
    "NOBATCH": "batch_no",
    "BRAND": "brand",
    "JENISPRODUK": "product_type",
    "QTYPCS": "qty",
    "QTY": "qty",
    "JENISKEMASAN": "packaging",
    "SATUANBERATGR": "unit_weight",
    "SATUANBERAT": "unit_weight",
    "TOTALKEBUTUHANBAHANGR": "total_material",
    "TOTALKEBUTUHANBAHAN": "total_material",
    "TGLPRODUKSI": "production_date",
    "PROSESMIXING": "mixing_state",
    "PROSESFILLING": "filling_state",
    "PROSESPELABELAN": "labeling_state",
    "PROSESLABELING": "labeling_state",
    "PROSESPACKING": "packing_state",
    "KIRIM": "delivery_state",
    "TGLSIAPPRODUKSI": "ready_date",
    "TGLKIRIM": "delivery_date",
    "STATUSPO": "po_status",
}
DATE_FIELDS = {"po_date", "production_date", "ready_date", "delivery_date"}
NUMBER_FIELDS = {"qty", "unit_weight", "total_material"}
PROCESS_FIELDS = {"mixing_state", "filling_state", "labeling_state", "packing_state", "delivery_state"}
PO_STATUS = {"SELESAI": "selesai", "PROGRESS": "progress", "PARTIAL": "partial", "CLOSING": "closing"}


def _norm(value):
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _text(value):
    if value is None:
        return False
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    return text or False


def _date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _text(value)
    if not text:
        return False
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return False  # mis. hanya angka tahun "2026": dianggap kosong


def _number(value):
    if isinstance(value, (int, float)):
        return float(value)
    text = _text(value)
    if not text:
        return 0.0
    try:
        return float(text.replace(".", "").replace(",", ".")) if "," in text else float(text)
    except ValueError:
        return 0.0


class ProductionReportImportWizard(models.TransientModel):
    _name = "mrp.production.report.import.wizard"
    _description = "Import Laporan Produksi"

    file = fields.Binary(string="File Excel (.xlsx)", required=True)
    filename = fields.Char()
    mode = fields.Selection(
        [
            ("update", "Tambah baru & perbarui yang sudah ada"),
            ("replace", "Hapus semua data lama, lalu import ulang"),
        ],
        string="Cara Import",
        default="update",
        required=True,
    )
    result = fields.Text(readonly=True)

    def _read_rows(self):
        try:
            workbook = load_workbook(io.BytesIO(base64.b64decode(self.file)), data_only=True, read_only=True)
        except Exception as error:
            raise UserError("File tidak bisa dibaca. Pastikan formatnya .xlsx.") from error
        rows = []
        for sheet in workbook.worksheets:
            header = None
            for values in sheet.iter_rows(values_only=True):
                if header is None:
                    keys = [HEADER_MAP.get(_norm(cell)) for cell in values]
                    if "po_number" in keys and "product_type" in keys:
                        header = keys
                    continue
                vals = {}
                for field_name, cell in zip(header, values):
                    if not field_name or field_name in vals:
                        continue
                    if field_name in DATE_FIELDS:
                        vals[field_name] = _date(cell)
                    elif field_name in NUMBER_FIELDS:
                        vals[field_name] = _number(cell)
                    elif field_name in PROCESS_FIELDS:
                        state = _norm(cell)
                        vals[field_name] = "done" if state == "DONE" else "progress" if state else False
                    elif field_name == "po_status":
                        vals[field_name] = PO_STATUS.get(_norm(cell), False)
                    else:
                        vals[field_name] = _text(cell)
                # Baris kosong (hanya sisa rumus) dilewati.
                if not (vals.get("po_number") or vals.get("brand") or vals.get("product_type")):
                    continue
                if not vals.get("total_material") and vals.get("qty") and vals.get("unit_weight"):
                    vals["total_material"] = vals["qty"] * vals["unit_weight"]
                rows.append(vals)
        if not rows:
            raise UserError(
                "Tidak ada data yang terbaca. Pastikan ada baris judul berisi kolom 'NO.PO' dan 'JENIS PRODUK'."
            )
        return rows

    def action_import(self):
        """Baris Excel dikelompokkan per No. PO: satu PO = satu data, berisi banyak produk."""
        self.ensure_one()
        Report = self.env["mrp.production.report"]
        Line = self.env["mrp.production.report.line"]
        company_domain = [("company_id", "in", [False, self.env.company.id])]
        rows = self._read_rows()
        if self.mode == "replace":
            Report.search(company_domain).unlink()

        # Satu PO = No. PO + Tgl PO. No. PO di Excel bisa terpakai ulang (mis. 010 di 2025 dan di 2026
        # untuk customer lain), jadi tanggal ikut membedakan.
        groups = {}
        for vals in rows:
            po_number = (vals.pop("po_number", False) or "").strip(" ;,.") or False
            po_date = vals.pop("po_date", False)
            key = ((po_number or "").upper(), po_date)
            group = groups.setdefault(key, {"po_number": po_number, "po_date": po_date, "lines": []})
            group["lines"].append(vals)

        reports = {
            ((r.po_number or "").upper(), r.po_date): r
            for r in Report.search(company_domain, order="id")
        }
        new_po = updated_po = new_lines = updated_lines = 0
        touched = Report
        for key, group in groups.items():
            report = reports.get(key)
            if report:
                updated_po += 1
            else:
                report = Report.create({"po_number": group["po_number"], "po_date": group["po_date"]})
                new_po += 1
            touched |= report
            # Produk dicocokkan per (Brand, Jenis Produk, Kemasan, Batch); yang kembar dicocokkan berurutan.
            existing = {}
            for line in report.line_ids.sorted("id"):
                existing.setdefault(line._import_key(), []).append(line)
            seen = {}
            to_create = []
            for index, vals in enumerate(group["lines"]):
                vals["sequence"] = (index + 1) * 10
                key = Line.new(vals)._import_key()
                position = seen.get(key, 0)
                seen[key] = position + 1
                matches = existing.get(key, [])
                if position < len(matches):
                    matches[position].write(vals)
                    updated_lines += 1
                else:
                    to_create.append({**vals, "report_id": report.id})
            if to_create:
                Line.create(to_create)
                new_lines += len(to_create)

        # Hubungkan ke Sales Order / Brand terdaftar / MOU. Yang belum cocok muncul di "Perlu Dipasangkan".
        touched.line_ids.action_auto_match()
        touched._auto_link_sale_order()
        self.result = f"PO: {new_po} baru, {updated_po} diperbarui · Baris dibaca: {len(rows)}"
        # Pratinjau dulu: produk baru dan Plan baru baru dibuat setelah disetujui.
        return self.env["ir.actions.act_window"]._for_xml_id(
            "custom_production_planning.action_production_report_line_preview"
        )
