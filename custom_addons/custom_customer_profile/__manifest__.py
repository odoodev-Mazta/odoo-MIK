{
    'name': 'Custom Customer Profile',
    'version': '1.0',
    'summary': 'Customer Profile Untuk Rekomendasi pada Dokter',
    'depends': ['base', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'views/customer_profile_views.xml',
        'views/product_views.xml',
        # 'views/res_partner_views.xml',
        'views/customer_profile_menus.xml',
    ],
    'installable': True,
    'application': False,
}