{
    "name": "Akses User",
    "author": "Staff Dev",
    "version": "19.0.1.2.0",
    "category": "Administration",
    "summary": "Atur akses setiap user per menu (Lihat, Buat, Ubah, Hapus, Setuju) dan peran modul",
    "depends": ["base", "web"],
    "data": [
        "security/ir.model.access.csv",
        "views/user_access_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "custom_user_access/static/src/matrix/access_matrix.js",
            "custom_user_access/static/src/matrix/access_matrix.xml",
            "custom_user_access/static/src/matrix/access_matrix.scss",
        ],
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
