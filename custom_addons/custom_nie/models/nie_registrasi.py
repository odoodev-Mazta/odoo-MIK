from odoo import models,fields,api

class NIERegistrasi(models.Model):
    _name = 'nie.registrasi'
    _description = 'NIE Registrasi'

    @api.model
    def get_dashboard_data(self):
        # 1. Dummy Progress Bar (Persentase langsung diketik manual)
        dummy_progress = {
            'start_reg': 35,  # 35%
            'revisi': 15,  # 15%
            'ditolak': 10,  # 10%
            'teregist': 40,  # 40%
        }

        # 2. Dummy Table Data (List of Dictionaries)
        dummy_table = [
            {
                'tgl': '2026-04-21',
                'pelanggan': 'PT Cahaya Abadi',
                'brand': 'SuperBrand X',
                'status': 'Start Registrasi',
                'tgl_terbit': '-',
                'masa_berakhir': '-',
                'attachment': 'Ada'
            },
            {
                'tgl': '2026-04-20',
                'pelanggan': 'CV Maju Bersama',
                'brand': 'Natura Herbal',
                'status': 'Revisi',
                'tgl_terbit': '-',
                'masa_berakhir': '-',
                'attachment': 'Tidak Ada'
            },
            {
                'tgl': '2026-04-18',
                'pelanggan': 'PT Sehat Sentosa',
                'brand': 'Vitaplus',
                'status': 'Ditolak',
                'tgl_terbit': '-',
                'masa_berakhir': '-',
                'attachment': 'Ada'
            },
            {
                'tgl': '2026-04-15',
                'pelanggan': 'Bintang Medika',
                'brand': 'CureAll',
                'status': 'Teregistrasi',
                'tgl_terbit': '2026-04-20',
                'masa_berakhir': '2031-04-20',
                'attachment': 'Ada'
            },
            {
                'tgl': '2026-04-10',
                'pelanggan': 'Apotek K-24',
                'brand': 'DermaGlow',
                'status': 'Teregistrasi',
                'tgl_terbit': '2026-04-12',
                'masa_berakhir': '2031-04-12',
                'attachment': 'Ada'
            }
        ]

        # Return format dictionary yang persis sama dengan ekspektasi OWL JS Anda
        return {
            'progress': dummy_progress,
            'table_data': dummy_table
        }