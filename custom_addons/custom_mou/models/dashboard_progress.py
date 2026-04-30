from odoo import models, fields, api

class DashboardProgress(models.AbstractModel):
    _name = 'dashboard.progress.mou'
    _description = 'Dashboard Progress MOU'

    @api.model
    def get_progress_data(self):
        stages = ['Biaya Register', 'DP', 'NIE', 'Bahan Baku', 'Kemasan', 'Produksi', 'Delivery']
        bar_chart_data =  {
            'labels': stages,
            'done': [45, 40, 35, 25, 20, 15, 10],
            'not_yet': [5, 10, 15, 25, 30, 35, 40],
        }

        mou_list = [
            {
                'id': 1, 'no_mou': 'MOU/2026/001', 'pelanggan': 'PT Maju Jaya', 'brand': 'GlowSkin',
                'progress': 30,
                'stages': [
                    {'tahapan': 'Biaya Register', 'deadline': '01-04-2026', 'is_dana_masuk': True,
                     'tgl_dana': '01-04-2026', 'is_start': True, 'tgl_start': '01-04-2026', 'is_done': True,
                     'tgl_done': '02-04-2026', 'overdue': 'Ontime'},
                    {'tahapan': 'DP', 'deadline': '05-04-2026', 'is_dana_masuk': True, 'tgl_dana': '04-04-2026',
                     'is_start': True, 'tgl_start': '04-04-2026', 'is_done': True, 'tgl_done': '05-04-2026',
                     'overdue': 'Ontime'},
                    {'tahapan': 'NIE', 'deadline': '20-04-2026', 'is_dana_masuk': False, 'tgl_dana': '-',
                     'is_start': True, 'tgl_start': '10-04-2026', 'is_done': False, 'tgl_done': '-',
                     'overdue': 'Ontime'},
                    {'tahapan': 'Bahan Baku', 'deadline': '10-05-2026', 'is_dana_masuk': False, 'tgl_dana': '-',
                     'is_start': False, 'tgl_start': '-', 'is_done': False, 'tgl_done': '-', 'overdue': '-'},
                    {'tahapan': 'Kemasan', 'deadline': '20-05-2026', 'is_dana_masuk': False, 'tgl_dana': '-',
                     'is_start': False, 'tgl_start': '-', 'is_done': False, 'tgl_done': '-', 'overdue': '-'},
                    {'tahapan': 'Produksi', 'deadline': '15-06-2026', 'is_dana_masuk': False, 'tgl_dana': '-',
                     'is_start': False, 'tgl_start': '-', 'is_done': False, 'tgl_done': '-', 'overdue': '-'},
                    {'tahapan': 'Delivery', 'deadline': '25-06-2026', 'is_dana_masuk': False, 'tgl_dana': '-',
                     'is_start': False, 'tgl_start': '-', 'is_done': False, 'tgl_done': '-', 'overdue': '-'}
                ]
            },
            {
                'id': 2, 'no_mou': 'MOU/2026/002', 'pelanggan': 'CV Abadi Bersama', 'brand': 'HerbalLife',
                'progress': 15,
                'stages': [
                    {'tahapan': 'Biaya Register', 'deadline': '10-04-2026', 'is_dana_masuk': True,
                     'tgl_dana': '09-04-2026', 'is_start': True, 'tgl_start': '09-04-2026', 'is_done': True,
                     'tgl_done': '10-04-2026', 'overdue': 'Ontime'},
                    {'tahapan': 'DP', 'deadline': '15-04-2026', 'is_dana_masuk': False, 'tgl_dana': '-',
                     'is_start': True, 'tgl_start': '11-04-2026', 'is_done': False, 'tgl_done': '-',
                     'overdue': 'Overdue'},
                    {'tahapan': 'NIE', 'deadline': '30-04-2026', 'is_dana_masuk': False, 'tgl_dana': '-',
                     'is_start': False, 'tgl_start': '-', 'is_done': False, 'tgl_done': '-', 'overdue': '-'},
                    {'tahapan': 'Bahan Baku', 'deadline': '15-05-2026', 'is_dana_masuk': False, 'tgl_dana': '-',
                     'is_start': False, 'tgl_start': '-', 'is_done': False, 'tgl_done': '-', 'overdue': '-'},
                    {'tahapan': 'Kemasan', 'deadline': '25-05-2026', 'is_dana_masuk': False, 'tgl_dana': '-',
                     'is_start': False, 'tgl_start': '-', 'is_done': False, 'tgl_done': '-', 'overdue': '-'},
                    {'tahapan': 'Produksi', 'deadline': '20-06-2026', 'is_dana_masuk': False, 'tgl_dana': '-',
                     'is_start': False, 'tgl_start': '-', 'is_done': False, 'tgl_done': '-', 'overdue': '-'},
                    {'tahapan': 'Delivery', 'deadline': '30-06-2026', 'is_dana_masuk': False, 'tgl_dana': '-',
                     'is_start': False, 'tgl_start': '-', 'is_done': False, 'tgl_done': '-', 'overdue': '-'}
                ]
            },
            {
                'id': 3, 'no_mou': 'MOU/2026/003', 'pelanggan': 'PT Sentosa Alam', 'brand': 'NaturaCare',
                'progress': 65,
                'stages': [
                    {'tahapan': 'Biaya Register', 'deadline': '01-03-2026', 'is_dana_masuk': True,
                     'tgl_dana': '01-03-2026', 'is_start': True, 'tgl_start': '01-03-2026', 'is_done': True,
                     'tgl_done': '02-03-2026', 'overdue': 'Ontime'},
                    {'tahapan': 'DP', 'deadline': '05-03-2026', 'is_dana_masuk': True, 'tgl_dana': '05-03-2026',
                     'is_start': True, 'tgl_start': '05-03-2026', 'is_done': True, 'tgl_done': '06-03-2026',
                     'overdue': 'Ontime'},
                    {'tahapan': 'NIE', 'deadline': '20-03-2026', 'is_dana_masuk': True, 'tgl_dana': '18-03-2026',
                     'is_start': True, 'tgl_start': '18-03-2026', 'is_done': True, 'tgl_done': '19-03-2026',
                     'overdue': 'Ontime'},
                    {'tahapan': 'Bahan Baku', 'deadline': '10-04-2026', 'is_dana_masuk': True, 'tgl_dana': '08-04-2026',
                     'is_start': True, 'tgl_start': '08-04-2026', 'is_done': True, 'tgl_done': '09-04-2026',
                     'overdue': 'Ontime'},
                    {'tahapan': 'Kemasan', 'deadline': '20-04-2026', 'is_dana_masuk': False, 'tgl_dana': '-',
                     'is_start': True, 'tgl_start': '15-04-2026', 'is_done': False, 'tgl_done': '-',
                     'overdue': 'Ontime'},
                    {'tahapan': 'Produksi', 'deadline': '15-05-2026', 'is_dana_masuk': False, 'tgl_dana': '-',
                     'is_start': False, 'tgl_start': '-', 'is_done': False, 'tgl_done': '-', 'overdue': '-'},
                    {'tahapan': 'Delivery', 'deadline': '25-05-2026', 'is_dana_masuk': False, 'tgl_dana': '-',
                     'is_start': False, 'tgl_start': '-', 'is_done': False, 'tgl_done': '-', 'overdue': '-'}
                ]
            },
            {
                'id': 4, 'no_mou': 'MOU/2026/004', 'pelanggan': 'PT Semesta Jaya', 'brand': 'SemestaCare',
                'progress': 65,
                'stages': [
                    {'tahapan': 'Biaya Register', 'deadline': '03-03-2026', 'is_dana_masuk': True,
                     'tgl_dana': '04-03-2026', 'is_start': True, 'tgl_start': '05-03-2026', 'is_done': True,
                     'tgl_done': '02-03-2026', 'overdue': 'Ontime'},
                    {'tahapan': 'DP', 'deadline': '05-03-2026', 'is_dana_masuk': True, 'tgl_dana': '05-03-2026',
                     'is_start': True, 'tgl_start': '05-03-2026', 'is_done': True, 'tgl_done': '06-03-2026',
                     'overdue': 'Ontime'},
                    {'tahapan': 'NIE', 'deadline': '20-03-2026', 'is_dana_masuk': True, 'tgl_dana': '18-03-2026',
                     'is_start': True, 'tgl_start': '18-03-2026', 'is_done': True, 'tgl_done': '19-03-2026',
                     'overdue': 'Ontime'},
                    {'tahapan': 'Bahan Baku', 'deadline': '10-04-2026', 'is_dana_masuk': True, 'tgl_dana': '08-04-2026',
                     'is_start': True, 'tgl_start': '08-04-2026', 'is_done': True, 'tgl_done': '09-04-2026',
                     'overdue': 'Ontime'},
                    {'tahapan': 'Kemasan', 'deadline': '20-04-2026', 'is_dana_masuk': False, 'tgl_dana': '-',
                     'is_start': True, 'tgl_start': '15-04-2026', 'is_done': False, 'tgl_done': '-',
                     'overdue': 'Ontime'},
                    {'tahapan': 'Produksi', 'deadline': '15-05-2026', 'is_dana_masuk': False, 'tgl_dana': '-',
                     'is_start': False, 'tgl_start': '-', 'is_done': False, 'tgl_done': '-', 'overdue': '-'},
                    {'tahapan': 'Delivery', 'deadline': '25-05-2026', 'is_dana_masuk': False, 'tgl_dana': '-',
                     'is_start': False, 'tgl_start': '-', 'is_done': False, 'tgl_done': '-', 'overdue': '-'}
                ]
            },
            {
                'id': 5, 'no_mou': 'MOU/2026/005', 'pelanggan': 'PT Planet Angkasa', 'brand': 'AngkasaSkin',
                'progress': 65,
                'stages': [
                    {'tahapan': 'Biaya Register', 'deadline': '03-03-2026', 'is_dana_masuk': True,
                     'tgl_dana': '04-03-2026', 'is_start': True, 'tgl_start': '05-03-2026', 'is_done': True,
                     'tgl_done': '02-03-2026', 'overdue': 'Ontime'},
                    {'tahapan': 'DP', 'deadline': '05-03-2026', 'is_dana_masuk': True, 'tgl_dana': '05-03-2026',
                     'is_start': True, 'tgl_start': '05-03-2026', 'is_done': True, 'tgl_done': '06-03-2026',
                     'overdue': 'Ontime'},
                    {'tahapan': 'NIE', 'deadline': '20-03-2026', 'is_dana_masuk': True, 'tgl_dana': '18-03-2026',
                     'is_start': True, 'tgl_start': '18-03-2026', 'is_done': True, 'tgl_done': '19-03-2026',
                     'overdue': 'Ontime'},
                    {'tahapan': 'Bahan Baku', 'deadline': '10-04-2026', 'is_dana_masuk': True, 'tgl_dana': '08-04-2026',
                     'is_start': True, 'tgl_start': '08-04-2026', 'is_done': True, 'tgl_done': '09-04-2026',
                     'overdue': 'Ontime'},
                    {'tahapan': 'Kemasan', 'deadline': '20-04-2026', 'is_dana_masuk': False, 'tgl_dana': '-',
                     'is_start': True, 'tgl_start': '15-04-2026', 'is_done': False, 'tgl_done': '-',
                     'overdue': 'Ontime'},
                    {'tahapan': 'Produksi', 'deadline': '15-05-2026', 'is_dana_masuk': False, 'tgl_dana': '-',
                     'is_start': False, 'tgl_start': '-', 'is_done': False, 'tgl_done': '-', 'overdue': '-'},
                    {'tahapan': 'Delivery', 'deadline': '25-05-2026', 'is_dana_masuk': False, 'tgl_dana': '-',
                     'is_start': False, 'tgl_start': '-', 'is_done': False, 'tgl_done': '-', 'overdue': '-'}
                ]
            },
            {
                'id': 6, 'no_mou': 'MOU/2026/006', 'pelanggan': 'CV Gonjang Ganjing', 'brand': 'GonjangDerm',
                'progress': 15,
                'stages': [
                    {'tahapan': 'Biaya Register', 'deadline': '10-04-2026', 'is_dana_masuk': True,
                     'tgl_dana': '09-04-2026', 'is_start': True, 'tgl_start': '09-04-2026', 'is_done': True,
                     'tgl_done': '10-04-2026', 'overdue': 'Ontime'},
                    {'tahapan': 'DP', 'deadline': '15-04-2026', 'is_dana_masuk': False, 'tgl_dana': '-',
                     'is_start': True, 'tgl_start': '11-04-2026', 'is_done': False, 'tgl_done': '-',
                     'overdue': 'Overdue'},
                    {'tahapan': 'NIE', 'deadline': '30-04-2026', 'is_dana_masuk': False, 'tgl_dana': '-',
                     'is_start': False, 'tgl_start': '-', 'is_done': False, 'tgl_done': '-', 'overdue': '-'},
                    {'tahapan': 'Bahan Baku', 'deadline': '15-05-2026', 'is_dana_masuk': False, 'tgl_dana': '-',
                     'is_start': False, 'tgl_start': '-', 'is_done': False, 'tgl_done': '-', 'overdue': '-'},
                    {'tahapan': 'Kemasan', 'deadline': '25-05-2026', 'is_dana_masuk': False, 'tgl_dana': '-',
                     'is_start': False, 'tgl_start': '-', 'is_done': False, 'tgl_done': '-', 'overdue': '-'},
                    {'tahapan': 'Produksi', 'deadline': '20-06-2026', 'is_dana_masuk': False, 'tgl_dana': '-',
                     'is_start': False, 'tgl_start': '-', 'is_done': False, 'tgl_done': '-', 'overdue': '-'},
                    {'tahapan': 'Delivery', 'deadline': '30-06-2026', 'is_dana_masuk': False, 'tgl_dana': '-',
                     'is_start': False, 'tgl_start': '-', 'is_done': False, 'tgl_done': '-', 'overdue': '-'}
                ]
            },
        ]

        master_table_data = [
            {'id': 1, 'pelanggan': 'PT Maju Jaya', 'reg': 'Done', 'dp': 'Done', 'nie': 'Process', 'bahan': 'Not Yet',
             'kemasan': 'Not Yet', 'produksi': 'Not Yet', 'delivery': 'Not Yet'},
            {'id': 2, 'pelanggan': 'CV Abadi Bersama', 'reg': 'Done', 'dp': 'Process', 'nie': 'Not Yet',
             'bahan': 'Not Yet', 'kemasan': 'Not Yet', 'produksi': 'Not Yet', 'delivery': 'Not Yet'},
            {'id': 3, 'pelanggan': 'PT Sentosa Alam', 'reg': 'Done', 'dp': 'Done', 'nie': 'Done', 'bahan': 'Done',
             'kemasan': 'Process', 'produksi': 'Not Yet', 'delivery': 'Not Yet'},
            {'id': 4, 'pelanggan': 'PT Semesta Jaya', 'reg': 'Done', 'dp': 'Done', 'nie': 'Done', 'bahan': 'Done',
             'kemasan': 'Process', 'produksi': 'Not Yet', 'delivery': 'Not Yet'},
            {'id': 5, 'pelanggan': 'PT Planet Angkasa', 'reg': 'Done', 'dp': 'Done', 'nie': 'Done', 'bahan': 'Done',
             'kemasan': 'Process', 'produksi': 'Not Yet', 'delivery': 'Not Yet'},
            {'id': 6, 'pelanggan': 'CV Gonjang Ganjing', 'reg': 'Done', 'dp': 'Done', 'nie': 'Done', 'bahan': 'Done',
             'kemasan': 'Process', 'produksi': 'Not Yet', 'delivery': 'Not Yet'},
        ]

        return {
            'bar_chart': bar_chart_data,
            'mou_list': mou_list,
            'master_table': master_table_data  # Tambahkan ini
        }