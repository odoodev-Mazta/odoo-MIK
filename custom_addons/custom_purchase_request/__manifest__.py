{
    'name': 'Custom Purchase Request',
    'author': 'Staff Dev',
    'license': 'LGPL-3',
    'version': '1.1',
    'depends': ['purchase', 'web', 'base', 'hr', 'account', 'product', 'custom_usulandana', 'custom_ecatalogue', 'custom_mou', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/sequence.xml',
        'views/purchase_request_views.xml',
        'views/pr_timeline_views.xml',
        'views/purchase_order_views.xml',
        'views/detail_export_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'custom_purchase_request/static/src/js/purchase_request_list.js',
            'custom_purchase_request/static/src/xml/purchase_request_dashboard.xml',
            'custom_purchase_request/static/src/scss/purchase_request_dashboard.scss',
            'custom_purchase_request/static/src/js/pr_timeline_dashboard.js',
            'custom_purchase_request/static/src/xml/pr_timeline_dashboard.xml',
            'custom_purchase_request/static/src/scss/pr_timeline_dashboard.scss',
        ],
    },
    'installable': True,
    'application': False,
}