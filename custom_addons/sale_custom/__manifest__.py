{
    'name': 'Mazta Custom Sales Order',
    'version': '19.0.2.0.1',
    'depends': ['sale'],
    'data': [
        'security/ir.model.access.csv', # Jangan lupa buat juga hak akses tabelnya!
        'views/sale_order_views.xml',
        'views/mazta_order_views.xml',
        'views/mazta_order_wizard_views.xml',
        'data/ir_sequence_data.xml',
    ],
    
    'assets': {
        'web.assets_backend': [
            'https://cdn.jsdelivr.net/npm/chart.js',
            'sale_custom/static/src/js/dashboard.js',
            'sale_custom/static/src/xml/dashboard_template.xml',
        ],
    },
    
    'installable': True,
    'application': True,
    'auto_install': False,
}