from importlib.resources import _

from odoo import models,fields,api

class DesignUsulanInherit(models.Model):
    """Inherit dari design.usulan (custom_design)"""
    _inherit = "design.usulan"

    registrasi_produk_ids = fields.One2many(
        comodel_name='registrasi.produk',
        inverse_name='design_id',
        string="Registrasi Produk",
    )
    registrasi_produk_count = fields.Integer(
        string="Jumlah Registrasi Produk",
        compute="_compute_registrasi_produk_count",
    )

    @api.depends('registrasi_produk_ids')
    def _compute_registrasi_produk_count(self):
        for rec in self:
            rec.registrasi_produk_count = len(rec.registrasi_produk_ids)

    def action_view_registrasi_produk(self):
        """Smart button list Registrasi Produk yg memakai design ini"""
        self.ensure_one()
        return{
            'type': 'ir.actions.act_window',
            'name': _('Registrasi Produk'),
            'res_model': 'registrasi.produk',
            'view_mode': 'list,form',
            'domain': [('design_id', '=', self.id)],
            'context': {'default_design_id': self.id},
        }