{
    'name': 'Custom COA',
    'version': '1.0',
    'summary': 'Membatasi penggunaan Header Account di Journal Entries',
    'depends': ['account'],
    'data': [
        'views/account_account_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
}