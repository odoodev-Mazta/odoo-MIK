{
    'name': 'MOU - Project Tracking',
    'version': '1.0',
    'category': 'Project',
    'summary': 'Buat Project per MOU, dipecah per Sales Order, dengan tanggal dari PR, PO, Plan Produksi, dan Delivery',
    'description': """
Satu MOU menjadi satu Project. Tiap Sales Order di MOU itu menjadi task induk, dan di bawahnya
sub-task dari dokumen aslinya, dengan tanggal mengikuti dokumen.

Tahap awal: MOU disahkan, pembayaran (registrasi, DP, NIE, pengadaan, balance), registrasi brand,
registrasi produk (BPOM), sertifikasi halal, dan desain.

Per Sales Order:

* Purchase Request: tanggal usulan sampai estimasi.
* Purchase Order: satu task per baris barang, dari tanggal PO sampai barang datang.
* Plan Produksi: planned start sampai planned end.
* Delivery: jadwal sampai selesai kirim.

Tombol Project di form MOU membuat atau memperbarui Project.
""",
    'author': 'Mazta',
    'depends': [
        'project', 'sale', 'purchase', 'stock',
        'custom_ecatalogue', 'custom_mou', 'custom_registrasi', 'custom_design',
        'custom_purchase_request', 'custom_production_planning',
    ],
    'data': [
        'views/project_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
