{
    'name': 'Modul Custom Field Department',
    'version': '1.0',
    'category': 'Departments',
    'summary': 'Adding custom fields to Departments',
    'description': 'Modul ini digunakan untuk menambahkan custom field ke Departments.',
    'author': 'William Purba',
    'depends': ['base', 'web_enterprise', 'hr'],
    'data':[
        'security/ir.model.access.csv',
        'views/hr_department_views.xml',
    ],
    'auto_install': False,
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}