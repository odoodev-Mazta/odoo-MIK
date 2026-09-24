{
    'name': 'Custom Sales Marketing',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Custom Marketing Sequence on Sales Order',
    'depends': [
        'sale_management',
        'custom_production_planning',
    ],
    'data': [
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
}