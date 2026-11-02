{
    'name': 'Maklon Inventory Integration',
    'version': '19.0.1.0.1',
    'summary': 'Integrasi Draft MOU dengan Inventory',
    'description': """
Integrasi Draft Maklon ke Stock Picking
=======================================

Fitur:
- Menambahkan field No MOU pada Stock Picking
- Otomatis membuat Operations dari Draft Maklon
- Menambahkan informasi Tahap, Kemasan, HNA, dll pada Stock Move
    """,

    'author': 'Staff Dev',

    'category': 'Inventory',
    'license': 'LGPL-3',

    'depends': [
        'base',
        'stock',
        'sale_stock',
        'custom_ecatalogue',
        'custom_mou',
    ],

    'data': [

        'security/ir.model.access.csv',
        'views/stock_picking_views.xml',
        'views/stock_move_views.xml',

    ],

    'installable': True,
    'application': False,
    'auto_install': False,
}