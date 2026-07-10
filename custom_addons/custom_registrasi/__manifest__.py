{
    'name': 'Custom Registrasi BPOM & Halal',
    'version': '19.0.1.0.0',
    'category': 'Regulatory / Compliance',
    'summary': 'BPOM Brand (HAKI) and Product NIE Registration Workflow',
    'description': """
        Comprehensive compliance and workflow management module for BPOM
        (Indonesian FDA) and Halal registration. Integrates with custom_mou
        and custom_design modules.

        Features:
        - Brand/HAKI Registration workflow (registrasi.brand)
        - Product NIE Registration workflow (registrasi.produk)
        - Multi-tier approval system
        - SLA tracking for submissions
        - Finance payment workflow
        - BPOM review loop with confirmation counter
        - Automatic NIE linkage to product.template
    """,
    'author': 'staff dev',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'mail',
        'product',
        'custom_mou',
        # 'custom_design',
        'custom_ecatalogue',
    ],
    'data': [
        'security/ir.model.access.csv',
        # 'security/security.xml',
        'data/sequence_data.xml',
        'views/registrasi_brand_views.xml',
        'views/registrasi_produk_views.xml',
        'views/registrasi_produk_line_views.xml',
        'views/halal_registrasi_views.xml',
        'views/menu_views.xml',
        'views/dashboard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'custom_registrasi/static/src/lib/chart.umd.min.js',
            'custom_registrasi/static/src/dashboard_registrasi.xml',
            'custom_registrasi/static/src/dashboard_registrasi.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
