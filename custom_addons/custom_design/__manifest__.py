{
    'name': 'Custom Design',
    'version': '19.0.1.1.0',
    'category': 'Design',
    'summary': 'Design Request & Approval Module',
    'description': '''
        Modul manajemen usulan design dengan alur approval:
        Draft → On Progress → Approval Marketing → Approval Client → Approval RO
        → Upload Form Design → Done
        Integrasi otomatis dengan Draft MOU (custom_ecatalogue).
    ''',
    'author': 'Rizky Dion Mahesa Putra',
    'depends': [
        'base',
        'mail',
        'web_enterprise',
        'custom_registrasi',
        'custom_ecatalogue',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'views/dashboard_design_views.xml',
        'views/design_usulan_views.xml',
        'views/design_approval_views.xml',
        'views/design_reject_wizard_views.xml',
        'views/draft_maklon_design_inherit_views.xml',
        'views/design_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'custom_design/static/src/components/dashboard_design.js',
            'custom_design/static/src/components/dashboard_design.xml',
        ],
    },
    'auto_install': False,
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
