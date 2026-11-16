{
    "name": "Custom MRP Bill of Materials",
    "version": "19.0.1.3.0",
    "category": "Manufacturing",
    "author": "William Purba",
    "depends": [
        "mrp",
    ],
    "external_dependencies": {
        "python": ["openpyxl", "xlsxwriter"],
    },
    "data": [
        "security/ir.model.access.csv",
        "views/mrp_bom_views.xml",
        "views/mrp_bom_import_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "custom_bom/static/src/import_progress.js",
            "custom_bom/static/src/import_progress.xml",
        ],
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
