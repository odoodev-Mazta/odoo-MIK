{
    'name': 'Design',
    'version': '1.0',
    'category': 'Design',
    'summary': 'Design Request Module',
    'description': 'Modul ini digunakan untuk Usulan Design.',
    'author': 'William Purba',
    'depends': ['base', 'web_enterprise'],
    'data':[
        'security/ir.model.access.csv',
        'views/design_usulan_views.xml',
        'views/design_menus.xml',
    ],
    'assets':{
        'web.assets_backend': [
            'custom_design/static/src/components/dashboard_usulan_design.js',
            'custom_design/static/src/components/dashboard_usulan_design.xml',
        ]
    },
    'auto_install': False,
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}