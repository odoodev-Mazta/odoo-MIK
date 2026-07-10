{
    'name': 'E-Catalogue',
    'version': '1.0',
    'category': 'E-Catalogue',
    'summary': 'E-Catalogue Module for MOU Needs',
    'description': 'Modul ini digunakan untuk E-Catalogue.',
    'author': 'William Purba',
    'depends': ['base', 'web_enterprise', 'contacts', 'mail', 'product', 'uom', 'account'],
    'data':[
        'security/ecatalogue_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/draft_mou_views.xml',
        'views/ecatalogue_views.xml',
        'views/promo_views.xml',
        'views/master_data_brand_views.xml',
        'views/ecatalogue_menus.xml',
    ],
    'assets':{
        'web.assets_backend': [
            'custom_ecatalogue/static/src/components/ecatalogue_carousel/**/*',
            'custom_ecatalogue/static/src/components/css/ecatalogue_carousel.scss',
        ]
    },
    'auto_install': False,
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}