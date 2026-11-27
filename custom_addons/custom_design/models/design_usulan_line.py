from odoo import models, fields, api
from odoo.exceptions import UserError


KEMASAN_TYPE = [
    ('botol', 'Botol'),
    ('tube',    'Tube'),
    ('jar',     'Jar'),
    ('sachet',  'Sachet'),
    ('pump', 'Tube Pump'),
]


class DesignUsulanLine(models.Model):
    _name = 'design.usulan.line'
    _description = 'Baris Produk Usulan Design'
    _order = 'sequence, id'

    usulan_id = fields.Many2one(
        'design.usulan',
        string='Usulan Design',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)

    nama_produk = fields.Char(string='Nama Produk', required=True)
    kemasan = fields.Selection(KEMASAN_TYPE, string='Jenis Kemasan')
    keterangan = fields.Char(string='Keterangan')

    attachment = fields.Binary(string='Attachment', attachment=True)
    attachment_fname = fields.Char(string='Nama File')

    def action_preview_attachment(self):
        """Lihat attachment produk di popup dulu; unduh lewat tombol Download."""
        self.ensure_one()
        return self.env['design.file.preview'].open_for(self, 'attachment', self.attachment_fname)
