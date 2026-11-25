"""Cari produk jadi untuk data riwayat (Excel): produk dulu, lalu BOM, dan bila belum ada dibuatkan dengan penamaan baku."""
import re

SIZE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(GRAM|GR|G|KG|ML|L)\b", re.IGNORECASE)
UNITS = {"GRAM": "GR", "GR": "GR", "G": "GR", "KG": "KG", "ML": "ML", "L": "L"}


def norm(value):
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def size_label(text):
    """'TUBE 20 GR HUAXING' -> '20 GR'; '1 Kg' -> '1 KG'; tidak ada ukuran -> ''."""
    match = SIZE_RE.search(str(text or "").replace("\n", " "))
    if not match:
        return ""
    return f"{match.group(1).replace(',', '.')} {UNITS[match.group(2).upper()]}"


def standard_name(brand, kind, packaging=""):
    """Penamaan baku: MERK + JENIS PRODUK + UKURAN, huruf besar. Mis. 'FARINA SKINCARE MASKER WINE 25 GR'."""
    parts = [str(brand or "").strip(), str(kind or "").strip(), size_label(packaging)]
    return re.sub(r"\s+", " ", " ".join(p for p in parts if p)).upper()


def clean_name(raw):
    """Nama barang di Surat Jalan -> nama baku: buang tulisan dalam kurung, rapikan ukuran, huruf besar."""
    text = re.sub(r"\(.*?\)", " ", str(raw or "").replace("\n", " "))
    text = SIZE_RE.sub(lambda m: f"{m.group(1).replace(',', '.')} {UNITS[m.group(2).upper()]}", text)
    return re.sub(r"\s+", " ", text).strip().upper()


def product_index(env):
    """Semua produk jadi yang bisa dicocokkan: produk dijual, dan produk yang punya BOM. {nama_ternormalisasi: template}."""
    templates = env["product.template"].search([("sale_ok", "=", True)])
    templates |= env["mrp.bom"].search([]).product_tmpl_id
    index = {}
    for template in templates:
        index.setdefault(norm(template.name), template)
    return index


def find_or_create_product(env, name, index):
    """Produk bernama `name`: cari persis, lalu yang unik mirip; bila tidak ada dibuat baru. Return product.template."""
    key = norm(name)
    if not key:
        return env["product.template"]
    found = index.get(key)
    if not found:
        similar = [t for k, t in index.items() if len(k) > 8 and (key in k or k in key)]
        found = similar[0] if len(similar) == 1 else False
    if not found:
        found = env["product.template"].create({
            "name": name,
            "type": "consu",
            "is_storable": True,
            "sale_ok": True,
            "purchase_ok": False,
        })
    index[key] = found
    return found
