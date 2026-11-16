{
    "name": "Custom MRP Bill of Materials",
    "version": "19.0.1.1.2",
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
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
