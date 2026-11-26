{
    'name': 'Maklon - Integrasi Mazta Finance',
    'version': '1.0',
    'category': 'E-Catalogue',
    'summary': 'Terima Request Maklon dari Mazta Finance dan kabari balik saat MOU jadi',
    'description': """
Integrasi dua arah dengan Mazta Finance.

* Mazta Finance ke Odoo: POST /maklon/request membuat draft.maklon, dengan kunci finance_request_id.
* Odoo ke Mazta Finance: saat draft.maklon menjadi MOU, kirim callback berisi request_id, status, nomor MOU, brand, dan customer, dengan antrean ulang otomatis.

Alamat, token, dan secret disimpan di System Parameters, bukan di kode.
""",
    'author': 'Mazta',
    'depends': ['custom_ecatalogue'],
    'data': [
        'data/ir_config_parameter.xml',
        'data/ir_cron.xml',
        'views/draft_maklon_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
