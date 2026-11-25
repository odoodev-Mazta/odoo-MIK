"""Cari produk jadi untuk data riwayat (Excel): produk dulu, lalu BOM, dan bila belum ada dibuatkan dengan penamaan baku."""
import re

SIZE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(GRAM|GR|G|KG|ML|L)\b", re.IGNORECASE)
UNITS = {"GRAM": "GR", "GR": "GR", "G": "GR", "KG": "KG", "ML": "ML", "L": "L"}


# Bahan kemasan / label / dummy bukan produk jadi: jangan ikut dicocokkan.
COMPONENT_RE = re.compile(
    r"^\s*(DUMMY|LABEL|STIKER|STICKER|SACHET|TUBE|JAR|BOTOL|MASTER\s*BOX|INNER|OUTER|BOX|DUS|KARTON|"
    r"PRINTING|SEAL|PUMP|AIRLESS|AIRPLESS)\b",
    re.IGNORECASE,
)


def is_component(name):
    return bool(COMPONENT_RE.match(str(name or "")))


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
        if is_component(template.name):
            continue
        index.setdefault(norm(template.name), template)
    return index


def _norm_brand(value):
    return norm(value)


def kind_key(text):
    """Jenis produk ternormalisasi: 'MASKER AGING', 'Masker Aging', 'DECONGEL D2' -> 'MASKERAGING', 'DECONGEL'."""
    return norm(re.sub(r"\bD2\b", " ", str(text or "").upper()))


def kind_from_name(raw):
    """Jenis dari keterangan dalam kurung di Surat Jalan: 'Miuna Aging Care Mask (Masker Aging) 20 gr' -> 'MASKERAGING'."""
    match = re.search(r"\(([^)]*)\)", str(raw or "").replace("\n", " "))
    if not match:
        return ""
    key = kind_key(match.group(1))
    known = ("MASKER", "DECONGEL", "SUNCREAM", "MOISTURIZER", "WHITENINGBALM", "NIACARE", "GLYCOCARE", "FACEWASH")
    return key if key.startswith(known) else ""


def find_product(index, name):
    """Cari produk jadi bernama `name`: persis, atau yang unik mirip. False bila tidak ada."""
    key = norm(name)
    if not key:
        return False
    found = index.get(key)
    if found:
        return found
    similar = [
        t for k, t in index.items()
        if len(k) > 8 and (key in k or k in key) and _digits(k) == _digits(key)
    ]
    if len(similar) == 1:
        return similar[0]
    return _closest(index, key)


def _digits(key):
    return "".join(re.findall(r"\d+", key))


def _closest(index, key):
    """Nama yang sangat mirip (salah ketik seperti DERCON/DECON). Angka (ukuran) harus sama, dan pemenang harus jelas."""
    import difflib

    scored = sorted(
        (
            (difflib.SequenceMatcher(None, key, k).ratio(), t)
            for k, t in index.items()
            if k[:3] == key[:3] and _digits(k) == _digits(key)
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    if scored and scored[0][0] >= 0.9 and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.03):
        return scored[0][1]
    return False


def find_or_create_product(env, name, index):
    """Produk bernama `name`: cari persis, lalu yang unik mirip; bila tidak ada dibuat baru. Return product.template."""
    key = norm(name)
    if not key:
        return env["product.template"]
    found = find_product(index, name)
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
