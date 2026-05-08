{
    'name': 'Modul Custom Field Data Vendor',
    'version': '1.0',
    'category': 'Contacts',
    'summary': 'Adding custom fields to Contacts',
    'description': 'Modul ini digunakan untuk menambahkan custom field ke Vendor.',
    'author': 'William Purba',
    'depends': ['base', 'web_enterprise', 'hr'],
    'data':[
        'views/contact_views.xml',
    ],
    'auto_install': False,
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}