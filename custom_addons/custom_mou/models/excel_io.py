"""Pembantu baca/tulis file Excel (.xlsx) untuk fitur Import & Export.

Dipakai oleh Sales Order (custom_mou) dan Delivery (custom_delivery).
Kolom didefinisikan sebagai (key, judul, lebar). Judul berakhiran * = wajib.
"""
import io
from datetime import date, datetime

import xlsxwriter
from openpyxl import load_workbook

XLSX_MIMETYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def build_workbook(sheets, help_lines=None):
    """sheets: [(nama_sheet, kolom, baris[dict])]. Kembalikan isi file .xlsx (bytes)."""
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    header_fmt = workbook.add_format({
        "bold": True, "bg_color": "#D9E1F2", "border": 1, "valign": "vcenter", "text_wrap": True,
    })
    required_fmt = workbook.add_format({
        "bold": True, "bg_color": "#FFE699", "border": 1, "valign": "vcenter", "text_wrap": True,
    })
    for sheet_name, columns, rows in sheets:
        sheet = workbook.add_worksheet(sheet_name)
        for col, (_key, title, width) in enumerate(columns):
            sheet.write(0, col, title, required_fmt if title.endswith("*") else header_fmt)
            sheet.set_column(col, col, width)
        sheet.freeze_panes(1, 0)
        for row_no, row in enumerate(rows, start=1):
            for col, (key, _title, _width) in enumerate(columns):
                value = row.get(key)
                sheet.write(row_no, col, "" if value in (None, False) else value)
    if help_lines:
        sheet = workbook.add_worksheet("Petunjuk")
        sheet.set_column(0, 0, 100)
        bold = workbook.add_format({"bold": True})
        for row_no, line in enumerate(help_lines):
            sheet.write(row_no, 0, line, bold if row_no == 0 else None)
    workbook.close()
    return output.getvalue()


def _norm(title):
    return str(title or "").replace("*", "").strip().lower()


def load(raw):
    return load_workbook(io.BytesIO(raw), data_only=True, read_only=True)


def parse_sheet(workbook, sheet_name, columns):
    """Baca satu sheet menjadi list dict (+ '_row' = nomor baris Excel)."""
    if sheet_name not in workbook.sheetnames:
        raise ValueError(
            f"Sheet '{sheet_name}' tidak ditemukan. Gunakan tombol Format Import untuk mengunduh formatnya."
        )
    rows = workbook[sheet_name].iter_rows(values_only=True)
    header = next(rows, None)
    if not header:
        raise ValueError(f"Sheet {sheet_name} kosong.")
    index = {_norm(title): pos for pos, title in enumerate(header) if title is not None}
    positions, missing = {}, []
    for key, title, _width in columns:
        pos = index.get(_norm(title))
        if pos is None:
            if title.endswith("*"):
                missing.append(title)
            continue
        positions[key] = pos
    if missing:
        raise ValueError(
            f"Sheet {sheet_name}: kolom {', '.join(missing)} tidak ditemukan. "
            f"Gunakan tombol Format Import untuk mengunduh formatnya."
        )
    result = []
    for line_no, values in enumerate(rows, start=2):
        row = {key: (values[pos] if pos < len(values) else None) for key, pos in positions.items()}
        if all(value in (None, "") for value in row.values()):
            continue
        row["_row"] = line_no
        result.append(row)
    return result


def to_text(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def to_number(value):
    """Angka dari sel Excel; None bila kosong. ValueError bila bukan angka."""
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value).strip().replace(",", "."))


def to_date(value):
    """Tanggal dari sel Excel (tanggal asli, atau teks YYYY-MM-DD / DD/MM/YYYY); None bila kosong."""
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    raise ValueError(text)


def download_action(env, filename, content):
    """Simpan file sebagai attachment sementara (diganti tiap kali) lalu unduh."""
    Attachment = env["ir.attachment"]
    Attachment.search([
        ("res_model", "=", False),
        ("name", "=", filename),
        ("create_uid", "=", env.uid),
    ]).unlink()
    attachment = Attachment.create({
        "name": filename,
        "type": "binary",
        "raw": content,
        "mimetype": XLSX_MIMETYPE,
    })
    return {
        "type": "ir.actions.act_url",
        "url": f"/web/content/{attachment.id}?download=true",
        "target": "self",
    }
