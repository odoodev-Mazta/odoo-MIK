{
    'name': 'Custom Purchase Request',
    'version': '1.0',
    'depends': ['purchase', 'web', 'base', 'hr', 'account', 'product', 'custom_usulandana'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/purchase_request_views.xml',
        'views/pr_timeline_views.xml',
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