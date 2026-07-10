from odoo import fields, models


class HalalRegistrasiLini(models.Model):
    _name = 'halal.registrasi.line'
    _description = 'Lini Produk – Registrasi Halal'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Urutan', default=10)

    halal_id = fields.Many2one(
        comodel_name='halal.registrasi',
        string='Registrasi Halal',
        required=True,
        ondelete='cascade',
        index=True,
    )

    nama_produk = fields.Char(string='Nama Produk', required=True)
    merek = fields.Char(string='Merek')
    varian = fields.Char(string='Varian / Tipe')
    netto = fields.Integer(string='Netto (g/ml)')

    kategori_bahan = fields.Selection(
        selection=[
            ('nabati', 'Nabati'),
            ('hewani', 'Hewani'),
            ('sintetis', 'Sintetis / Kimia'),
            ('campuran', 'Campuran'),
        ],
        string='Kategori Bahan Utama',
    )
    status_bahan = fields.Selection(
        selection=[
            ('halal', 'Halal'),
            ('syubhat', 'Syubhat (Perlu Verifikasi)'),
            ('haram', 'Haram'),
        ],
        string='Status Bahan',
        default='halal',
    )
    keterangan = fields.Text(string='Keterangan')