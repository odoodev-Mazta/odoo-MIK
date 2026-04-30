from odoo import models, fields, api

class DashboardMou(models.AbstractModel):
    _name = 'dashboard.mou'
    _description = 'Dashboard for MOU'

    @api.model
    def get_dashboard_statistics(self):
        return {
            'stats': {'total_users': 12, 'system_status': 'Active'},
            'chart_1': {'labels': ['MOU (Signed)', 'Draft'], 'data': [120, 45]},
            'chart_2': {'labels': ['MOU', 'Cancel'], 'data': [155, 10]},
            'chart_3': {'labels': ['Sudah DP', 'Belum DP / Pending'], 'data': [85, 35]},
            'chart_4': {'labels': ['Aman (> 30 Hari)', 'Mendesak (< 30 Hari)', 'Overdue'], 'data': [60, 25, 10]},

            # Data Tabel Baru sesuai Header
            'table_data': [
                {
                    'id': 1, 'tgl_draft': '01-04-2026', 'tgl_mou': '15-04-2026',
                    'pelanggan': 'PT Maju Jaya', 'produk': 'Sistem ERP', 'qty': 1,
                    'dp': '50%', 'bp': '50%', 'deadline_delivery': '30-05-2026',
                    # Key untuk filter Chart (Hidden/Digunakan Logika JS)
                    'status': 'MOU (Signed)', 'cancel_status': 'MOU', 'dp_status': 'Sudah DP',
                    'deadline_cat': 'Aman (> 30 Hari)'
                },
                {
                    'id': 2, 'tgl_draft': '10-04-2026', 'tgl_mou': '-',
                    'pelanggan': 'CV Abadi Bersama', 'produk': 'Website E-Commerce', 'qty': 1,
                    'dp': '0%', 'bp': '100%', 'deadline_delivery': '25-04-2026',
                    'status': 'Draft', 'cancel_status': 'MOU', 'dp_status': 'Belum DP / Pending',
                    'deadline_cat': 'Mendesak (< 30 Hari)'
                },
                {
                    'id': 3, 'tgl_draft': '20-03-2026', 'tgl_mou': '25-03-2026',
                    'pelanggan': 'PT Sentosa Alam', 'produk': 'Aplikasi Mobile', 'qty': 2,
                    'dp': '30%', 'bp': '70%', 'deadline_delivery': '10-04-2026',
                    'status': 'MOU (Signed)', 'cancel_status': 'Cancel', 'dp_status': 'Sudah DP',
                    'deadline_cat': 'Overdue'
                },
            ]
        }