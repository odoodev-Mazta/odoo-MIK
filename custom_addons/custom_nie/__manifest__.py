{
    'name': 'NIE',
    'version': '1.0',
    'category': 'NIE',
    'summary': 'NIE Module',
    'description': 'Modul ini digunakan untuk NIE.',
    'author': 'William Purba',
    'depends': ['base', 'web_enterprise'],
    'data':[
        'security/ir.model.access.csv',
        'views/nie_reporting_views.xml',
        'views/nie_menus.xml',
    ],
    'assets':{
        'web.assets_backend': [
            'custom_nie/static/src/components/nie_reporting_dashboard.js',
            'custom_nie/static/src/components/nie_reporting_dashboard.xml',
        ]
    },
    'auto_install': False,
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}