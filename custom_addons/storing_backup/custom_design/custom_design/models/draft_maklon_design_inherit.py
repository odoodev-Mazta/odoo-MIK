from odoo import models, fields, api, _


class DraftMaklonDesignInherit(models.Model):
    _inherit = 'draft.maklon'

    design_usulan_ids = fields.One2many(
        'design.usulan',
        'mou_id',
        string='Usulan Design',
    )
    design_usulan_count = fields.Integer(
        string='Jumlah Usulan Design',
        compute='_compute_design_usulan_count',
    )

    @api.depends('design_usulan_ids')
    def _compute_design_usulan_count(self):
        for rec in self:
            rec.design_usulan_count = len(rec.design_usulan_ids)

    def action_confirm_mou(self):
        """Override: konfirmasi MOU → buat Usulan Design → redirect ke form Usulan."""
        # Jalankan logic asli dulu (ubah state ke 'mou', rename kode)
        super().action_confirm_mou()

        self.ensure_one()

        # Cek duplikat
        existing = self.env['design.usulan'].search([
            ('mou_id', '=', self.id)
        ], limit=1)

        if existing:
            usulan = existing
        else:
            # Kumpulkan produk dari maklon_line_ids
            product_lines = []
            for line in self.maklon_line_ids:
                nama = line.product.name if line.product else False
                if nama:
                    product_lines.append((0, 0, {
                        'nama_produk': nama,
                        'kemasan': line.kemasan or False,
                        'keterangan': line.ukuran or False,
                    }))

            # Buat Usulan Design baru
            usulan = self.env['design.usulan'].create({
                'partner_id': self.nama_cust.id if self.nama_cust else False,
                'mou_id': self.id,
                'brand': self.brand or False,
                'product_line_ids': product_lines,
            })

            self.message_post(body=_(
                'Usulan Design otomatis dibuat: <b>%s</b>'
            ) % usulan.name)

        # Langsung redirect ke form Usulan Design yang baru dibuat
        return {
            'type': 'ir.actions.act_window',
            'name': _('Usulan Design'),
            'res_model': 'design.usulan',
            'res_id': usulan.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_design_usulan(self):
        """Smart button → buka list Usulan Design terkait MOU ini."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Usulan Design'),
            'res_model': 'design.usulan',
            'view_mode': 'list,form',
            'domain': [('mou_id', '=', self.id)],
            'context': {
                'default_mou_id': self.id,
                'default_partner_id': self.nama_cust.id if self.nama_cust else False,
                'default_brand': self.brand or False,
            },
        }
