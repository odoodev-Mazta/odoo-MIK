# -*- coding: utf-8 -*-
{
    'name': 'RnD Formulation Lab',
    'version': '19.0.1.0.0',
    'category': 'Research and Development',
    'summary': 'Modul Pengujian Formulasi Obat/Laboratorium Tanpa BOM',
    'author': 'Michael Jones',
    'depends': ['base', 'mail', 'uom'],
    'data': [
        'security/ir.model.access.csv',
        'views/rnd_formula_views.xml',
        'views/rnd_dashboard_views.xml',  # <-- Tambahkan file XML Dashboard di sini
    ],
    'assets': {
        'web.assets_backend': [
            # Ganti 'rnd_lab' dengan nama folder modul Anda
            'rnd_formulation/static/src/xml/rnd_dashboard_template.xml',
            'rnd_formulation/static/src/js/rnd_dashboard.js',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}