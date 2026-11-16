"""Baca/tulis file Excel untuk Import & Export BoM.

Format file (dua sheet, satu baris = satu komponen):
  - BoM        : header BoM diulang di tiap baris komponen
  - Operations : satu baris = satu operation
"""
import io

import xlsxwriter
from openpyxl import load_workbook

SHEET_BOM = "BoM"
SHEET_OPS = "Operations"
SHEET_HELP = "Petunjuk"

# (key, judul kolom, lebar). Judul berakhiran * = wajib diisi.
BOM_COLUMNS = [
    ("product_code", "Kode Produk Jadi*", 20),
    ("product_name", "Nama Produk Jadi", 34),
    ("product_qty", "Qty Produk Jadi", 16),
    ("bom_type", "Tipe BoM", 12),
    ("bom_code", "Referensi BoM", 18),
    ("brand", "Brand", 18),
    ("variant", "Varian Produk", 18),
    ("jenis_produk", "Jenis Produk", 20),
    ("jenis_kemasan", "Jenis Kemasan", 24),
    ("comp_code", "Kode Komponen*", 20),
    ("comp_name", "Nama Komponen", 34),
    ("comp_qty", "Qty Komponen*", 15),
    ("comp_uom", "Satuan Komponen", 16),
]

OP_COLUMNS = [
    ("product_code", "Kode Produk Jadi*", 20),
    ("bom_code", "Referensi BoM", 18),
    ("name", "Operation*", 26),
    ("workcenter", "Work Center*", 26),
    ("duration", "Durasi (menit)", 16),
    ("sequence", "Urutan", 10),
]

HELP_LINES = [
    "PETUNJUK IMPORT BoM",
    "",
    "Sheet BoM (satu baris = satu komponen)",
    "  - Kode Produk Jadi*  : Internal Reference produk jadi (harus sudah ada di Odoo).",
    "  - Qty Produk Jadi    : jumlah yang dihasilkan resep ini. Kosong = 1.",
    "  - Tipe BoM           : normal (Manufacture) atau kit. Kosong = normal.",
    "  - Referensi BoM      : kode BoM (opsional). Isi bila satu produk punya lebih dari satu BoM.",
    "  - Kode Komponen*     : Internal Reference bahan/label/kemasan (harus sudah ada di Odoo).",
    "  - Qty Komponen*      : jumlah komponen untuk Qty Produk Jadi.",
    "  - Satuan Komponen    : nama satuan (mis. Unit, kg, g). Kosong = satuan bawaan produk.",
    "  - Jenis Produk / Jenis Kemasan : opsional; bila belum ada di Odoo otomatis dibuatkan.",
    "  - Data header (produk jadi, qty, tipe, brand, varian) diulang di tiap baris komponen;",
    "    yang dipakai adalah baris pertama untuk setiap produk + Referensi BoM.",
    "",
    "Sheet Operations (opsional, satu baris = satu operation)",
    "  - Kode Produk Jadi* dan Referensi BoM harus sama dengan di sheet BoM.",
    "  - Operation*  : nama langkah kerja (Penimbangan, Mixing, Filling, dst.).",
    "  - Work Center*: nama work center yang sudah ada di Odoo.",
    "  - Durasi (menit) kosong = 60. Urutan kosong = mengikuti urutan baris.",
    "",
    "Aturan",
    "  - Semua baris diperiksa dulu. Jika ada satu saja yang salah, tidak ada yang diimpor.",
    "  - Baris contoh di file Format Import hanya contoh: hapus atau ganti dengan data asli.",
    "  - Export BoM menghasilkan file dengan format yang sama, jadi bisa diedit lalu diimpor lagi.",
]

SAMPLE_BOM_ROWS = [
    {"product_code": "MZM-003", "product_name": "Hyal Soothing Modeling Mask", "product_qty": 1,
     "bom_type": "normal", "bom_code": "", "brand": "", "variant": "",
     "comp_code": "RM-001", "comp_name": "Contoh bahan baku", "comp_qty": 0.25, "comp_uom": "kg"},
    {"product_code": "MZM-003", "product_name": "Hyal Soothing Modeling Mask", "product_qty": 1,
     "bom_type": "normal", "bom_code": "", "brand": "", "variant": "",
     "comp_code": "PM-001", "comp_name": "Contoh kemasan", "comp_qty": 1, "comp_uom": "Unit"},
]

SAMPLE_OP_ROWS = [
    {"product_code": "MZM-003", "bom_code": "", "name": "Penimbangan",
     "workcenter": "Ruang Timbang", "duration": 30, "sequence": 10},
    {"product_code": "MZM-003", "bom_code": "", "name": "Mixing",
     "workcenter": "Mixer Powder", "duration": 60, "sequence": 20},
]


def build_workbook(bom_rows, op_rows, with_help=False):
    """Kembalikan isi file .xlsx (bytes)."""
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    header_fmt = workbook.add_format({
        "bold": True, "bg_color": "#D9E1F2", "border": 1, "valign": "vcenter", "text_wrap": True,
    })
    required_fmt = workbook.add_format({
        "bold": True, "bg_color": "#FFE699", "border": 1, "valign": "vcenter", "text_wrap": True,
    })
    for sheet_name, columns, rows in (
        (SHEET_BOM, BOM_COLUMNS, bom_rows),
        (SHEET_OPS, OP_COLUMNS, op_rows),
    ):
        sheet = workbook.add_worksheet(sheet_name)
        for col, (_key, title, width) in enumerate(columns):
            sheet.write(0, col, title, required_fmt if title.endswith("*") else header_fmt)
            sheet.set_column(col, col, width)
        sheet.freeze_panes(1, 0)
        for row_no, row in enumerate(rows, start=1):
            for col, (key, _title, _width) in enumerate(columns):
                value = row.get(key)
                sheet.write(row_no, col, "" if value in (None, False) else value)
    if with_help:
        sheet = workbook.add_worksheet(SHEET_HELP)
        sheet.set_column(0, 0, 100)
        bold = workbook.add_format({"bold": True})
        for row_no, line in enumerate(HELP_LINES):
            sheet.write(row_no, 0, line, bold if row_no == 0 else None)
    workbook.close()
    return output.getvalue()


def _norm(title):
    return str(title or "").replace("*", "").strip().lower()


def _read_sheet(sheet, columns, sheet_name):
    rows = sheet.iter_rows(values_only=True)
    header = next(rows, None)
    if not header:
        raise ValueError(f"Sheet {sheet_name} kosong.")
    index = {_norm(title): pos for pos, title in enumerate(header) if title is not None}
    positions = {}
    missing = []
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


def _po_columns(header):
    """Petakan kolom file PO dari judulnya. None bila bukan format PO."""
    titles = [" ".join(str(t or "").lower().split()) for t in header]
    if not any("component" in t for t in titles) or "product" not in titles:
        return None
    pos = {"product": titles.index("product"), "comp": next(i for i, t in enumerate(titles) if "component" in t)}
    for key, test in (
        ("so", lambda t: t.replace(" ", "") in ("no.so", "noso")),
        ("qty", lambda t: t == "qty"),
        ("uom", lambda t: "unit of measure" in t and "bom lines" not in t),
        ("type", lambda t: t == "bom type"),
        ("jenis_produk", lambda t: t == "jenis produk"),
        ("jenis_kemasan", lambda t: t == "jenis kemasan"),
    ):
        found = [i for i, t in enumerate(titles) if test(t)]
        if found:
            pos[key] = found[0]
    # Sheet 2026: jenis produk ada di kolom kedua yang berjudul "QTY".
    qty_cols = [i for i, t in enumerate(titles) if t == "qty"]
    if "jenis_produk" not in pos and len(qty_cols) > 1:
        pos["jenis_produk"] = qty_cols[1]
    # Bisa ada dua kolom "BoM Lines/Quantity" (netto lalu total): yang dipakai yang terakhir.
    qty = [i for i, t in enumerate(titles) if "bom lines" in t and "quantity" in t]
    uom = [i for i, t in enumerate(titles) if "bom lines" in t and "unit" in t]
    if not qty or "qty" not in pos:
        return None
    pos["comp_qty"] = qty[-1]
    if uom:
        pos["comp_uom"] = uom[-1]
    return pos


def _parse_po_sheet(sheet, seen):
    """Satu blok = satu produk jadi (baris pertama) + baris komponen di bawahnya."""
    rows = list(sheet.iter_rows(values_only=True))
    pos = None
    start = 0
    for index, values in enumerate(rows[:10]):
        pos = _po_columns(values)
        if pos:
            start = index + 1
            break
    if not pos:
        return None

    def cell(values, key):
        i = pos.get(key)
        return values[i] if i is not None and i < len(values) else None

    result = []
    current = None
    for offset, values in enumerate(rows[start:]):
        line_no = start + offset + 1
        product = to_text(cell(values, "product"))
        comp = to_text(cell(values, "comp"))
        if product:
            so = to_text(cell(values, "so"))
            base = f"SO-{so}" if so else f"{sheet.title}-{line_no}"
            key = (product.lower(), base)
            seen[key] = seen.get(key, 0) + 1
            code = base if seen[key] == 1 else f"{base}-{seen[key]}"
            current = {
                "product_code": "", "product_name": product,
                "product_qty": cell(values, "qty"),
                "product_uom": to_text(cell(values, "uom")),
                "bom_type": to_text(cell(values, "type")).lower(),
                "bom_code": code, "brand": "", "variant": "",
                "jenis_produk": to_text(cell(values, "jenis_produk")),
                "jenis_kemasan": to_text(cell(values, "jenis_kemasan")),
            }
        elif current is None or not comp:
            continue
        row = dict(current)
        row.update({
            "comp_code": "", "comp_name": comp,
            "comp_qty": cell(values, "comp_qty"),
            "comp_uom": to_text(cell(values, "comp_uom")),
            "_row": line_no, "_sheet": sheet.title,
        })
        result.append(row)
    return result


def parse_workbook(raw):
    """Baca file .xlsx. Kembalikan (baris_bom, baris_operation).

    Mendukung Format Import (sheet BoM) dan file PO (blok per produk, tanpa kode produk).
    """
    workbook = load_workbook(io.BytesIO(raw), data_only=True, read_only=True)
    if SHEET_BOM not in workbook.sheetnames:
        seen = {}
        po_rows = []
        for sheet in workbook.worksheets:
            po_rows.extend(_parse_po_sheet(sheet, seen) or [])
        if not po_rows:
            raise ValueError(
                f"Sheet '{SHEET_BOM}' tidak ditemukan dan file tidak dikenali sebagai file PO. "
                f"Gunakan tombol Format Import untuk mengunduh formatnya."
            )
        return po_rows, []
    bom_rows = _read_sheet(workbook[SHEET_BOM], BOM_COLUMNS, SHEET_BOM)
    op_rows = []
    if SHEET_OPS in workbook.sheetnames:
        op_rows = _read_sheet(workbook[SHEET_OPS], OP_COLUMNS, SHEET_OPS)
    return bom_rows, op_rows


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
