import base64
import io
import re
from datetime import date, datetime

from openpyxl import load_workbook

from odoo import fields, models
from odoo.exceptions import UserError

HEADER_MAP = {
    "NOPO": "po_number",
    "NOMORSJ": "sj_number",
    "NOBATCHED": "batch_text",
    "NOBATCH": "batch_text",
    "NAMABARANG": "product_name",
    "SATUAN": "unit",
    "JUMLAHBARANG": "qty",
    "JUMLAHPACKING": "packing",
    "JUMLAHPACKAGING": "packing",
    "PRICE": "price",
    "VALUE": "value",
    "TANGGALPENGIRIMAN": "delivery_date",
    "KETERANGAN": "note",
    "NAMAUSER": "recipient",
    "NOTELP": "phone",
    "EKSPEDISI": "expedition",
    "ALAMAT": "address",
}
NUMBER_FIELDS = {"qty", "price", "value"}
MONTHS = {
    "JANUARI": 1, "FEBRUARI": 2, "MARET": 3, "APRIL": 4, "MEI": 5, "JUNI": 6, "JULI": 7,
    "AGUSTUS": 8, "SEPTEMBER": 9, "OKTOBER": 10, "NOVEMBER": 11, "DESEMBER": 12,
}


def _norm(value):
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _text(value):
    if value is None:
        return False
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = re.sub(r"\s+", " ", str(value).replace("\n", " ")).strip()
    return text or False


def _number(value):
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"\d[\d.,]*", str(value or ""))
    if not match:
        return 0.0
    raw = match.group(0)
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", ".")
    elif raw.count(".") > 1 or re.fullmatch(r"\d{1,3}\.\d{3}", raw):
        raw = raw.replace(".", "")
    try:
        return float(raw)
    except ValueError:
        return 0.0


def _date(value):
    """Tanggal Excel atau teks Indonesia, mis. '07 Januari 2026'."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    match = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", str(value or ""))
    if match and match.group(2).upper() in MONTHS:
        try:
            return date(int(match.group(3)), MONTHS[match.group(2).upper()], int(match.group(1)))
        except ValueError:
            return False
    return False


class DeliveryRecapImportWizard(models.TransientModel):
    _name = "mrp.delivery.recap.import.wizard"
    _description = "Import Rekapan Surat Jalan"

    file = fields.Binary(string="File Excel (.xlsx)", required=True)
    filename = fields.Char()
    result = fields.Text(readonly=True)

    def _read_rows(self):
        try:
            workbook = load_workbook(io.BytesIO(base64.b64decode(self.file)), data_only=True, read_only=True)
        except Exception as error:
            raise UserError("File tidak bisa dibaca. Pastikan formatnya .xlsx.") from error
        # Sheet bulanan diproses lebih dulu (ada harga). Sheet rangkuman "REKAPAN" hanya menambah yang belum ada.
        sheets = sorted(workbook.worksheets, key=lambda ws: ws.title.strip().upper().startswith("REKAPAN"))
        rows, seen = [], set()
        for sheet in sheets:
            header, sheet_rows = None, []
            for values in sheet.iter_rows(values_only=True):
                if header is None:
                    if values and _norm(values[0]) == "NO":
                        header = [HEADER_MAP.get(_norm(cell)) for cell in values]
                    continue
                vals = {}
                for field_name, cell in zip(header, values):
                    if not field_name or field_name in vals:
                        continue
                    if field_name == "delivery_date":
                        vals[field_name] = _date(cell)
                    elif field_name in NUMBER_FIELDS:
                        vals[field_name] = _number(cell)
                    else:
                        vals[field_name] = _text(cell)
                if not (vals.get("product_name") and (vals.get("sj_number") or vals.get("qty"))):
                    continue
                vals["sheet_name"] = sheet.title.strip()
                sheet_rows.append(vals)
            # Tanggal kosong diisi dari baris lain dengan Surat Jalan yang sama.
            dates = {}
            for vals in sheet_rows:
                if vals.get("delivery_date") and vals.get("sj_number"):
                    dates.setdefault(_norm(vals["sj_number"]), vals["delivery_date"])
            for vals in sheet_rows:
                if not vals.get("delivery_date") and vals.get("sj_number"):
                    vals["delivery_date"] = dates.get(_norm(vals["sj_number"]), False)
                key = (_norm(vals.get("sj_number")), _norm(vals.get("product_name")), _norm(vals.get("batch_text")))
                if key in seen:
                    continue
                seen.add(key)
                rows.append(vals)
        if not rows:
            raise UserError(
                "Tidak ada data yang terbaca. Pastikan ada baris judul yang diawali kolom 'No' "
                "dan berisi 'Nomor SJ' serta 'Nama Barang'."
            )
        return rows

    def action_import(self):
        self.ensure_one()
        Recap = self.env["mrp.delivery.recap"]
        rows = self._read_rows()
        existing = {}
        for rec in Recap.search([("company_id", "in", [False, self.env.company.id])], order="id"):
            existing.setdefault(rec._import_key(), []).append(rec)
        created = updated = 0
        touched = Recap
        for vals in rows:
            key = tuple(_norm(vals.get(f)) for f in ("sj_number", "product_name", "batch_text"))
            matches = existing.get(key)
            if matches:
                matches[0].write(vals)
                touched |= matches[0]
                updated += 1
            else:
                rec = Recap.create(vals)
                existing.setdefault(key, []).append(rec)
                touched |= rec
                created += 1
        touched.action_auto_match()
        pending = len(touched.filtered(lambda r: r.match_state == "pending"))
        self.result = (
            f"Baris baru: {created} · Diperbarui: {updated} · Dibaca: {len(rows)} · "
            f"Brand perlu dipasangkan: {pending}"
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Import Rekapan Surat Jalan",
                "message": self.result,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }
