from odoo import models, fields


class DesignRevisiLine(models.Model):
    _name = 'design.revisi.line'
    _description = 'Riwayat Revisi Design'
    _order = 'revisi_ke desc'

    usulan_id = fields.Many2one(
        'design.usulan',
        string='Usulan Design',
        required=True,
        ondelete='cascade',
    )
    revisi_ke = fields.Integer(string='Revisi ke-', readonly=True)
    tanggal = fields.Datetime(string='Tanggal', readonly=True, default=fields.Datetime.now)
    user_id = fields.Many2one('res.users', string='Oleh', readonly=True)
    state_from = fields.Char(string='Dari State', readonly=True)
    catatan = fields.Text(string='Catatan Revisi')
