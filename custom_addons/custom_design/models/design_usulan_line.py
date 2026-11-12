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
        """Buka file di tab baru untuk dilihat dulu (unduh lewat tombol di viewer browser)."""
        self.ensure_one()
        if not self.attachment:
            raise UserError('Belum ada file yang diunggah.')
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/design.usulan.line/{self.id}/attachment?download=false',
            'target': 'new',
        }
