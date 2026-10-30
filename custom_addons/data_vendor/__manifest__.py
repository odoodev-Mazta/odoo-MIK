{
    'name': 'Modul Additional Custom Field Data Vendor',
    'version': '1.0',
    'category': 'Additional Fields',
    'summary': 'Adding custom fields to Vendor',
    'description': 'Modul ini digunakan untuk menambahkan custom field ke Vendor.',
    'author': 'Your Name',
    'depends': ['base', 'web_enterprise', 'hr'], # web_enterprise agar tampilan tetap mode enterprise
    'data':[
        'security/ir.model.access.csv',
        'views/contact_views.xml',
    ],
    'auto_install': False,
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}