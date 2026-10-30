{
    'name': 'R&D',
    'version': '1.0',
    'category': 'R&D',
    'summary': 'R&D Module',
    'description': 'Modul ini digunakan untuk R&D.',
    'author': 'William Purba',
    'depends': ['base', 'web_enterprise', 'mail', 'hr'],
    'data':[
        'security/ir.model.access.csv',
        'views/rnd_formulation_views.xml',
        'views/rnd_menus.xml',
    ],
    'auto_install': False,
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}