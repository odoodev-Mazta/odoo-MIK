{
    'name': 'Custom Upgrade Tools',
    'version': '19.0.1.0.0',
    'summary': 'Upgrade semua modul custom sekaligus, dengan progress dan coba ulang',
    'description': """
Satu tombol di menu Apps untuk mengupgrade semua modul di folder custom_addons:

- Diupgrade satu per satu sesuai urutan ketergantungan modul
- Progress bar per modul
- Gagal sementara dicoba ulang otomatis, gagal karena kode bisa dicoba ulang manual
- Riwayat upgrade tersimpan
    """,
    'author': 'Staff Dev',
    'category': 'Administration',
    'license': 'LGPL-3',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/custom_upgrade_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'custom_upgrade_tools/static/src/upgrade_dashboard.js',
            'custom_upgrade_tools/static/src/upgrade_dashboard.xml',
        ],
    },
    'installable': True,
    'application': False,
}
