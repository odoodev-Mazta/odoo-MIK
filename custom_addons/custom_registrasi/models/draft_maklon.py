from odoo import api, fields, models


class DraftMaklon(models.Model):
    _inherit = 'draft.maklon'

    brand_reg_ids = fields.One2many('registrasi.brand', 'mou_id', string='Registrasi Brand')
    produk_reg_ids = fields.One2many('registrasi.produk', 'mou_id', string='Registrasi NIE')
    halal_reg_ids = fields.One2many('halal.registrasi', 'mou_id', string='Registrasi Halal')

    reg_brand_state = fields.Selection(
        selection=lambda self: [('none', 'Belum Didaftarkan')] + self.env['registrasi.brand']._fields['state']._description_selection(self.env),
        string='Status Brand', compute='_compute_registrasi_status', store=True)
    reg_nie_state = fields.Selection(
        selection=lambda self: [('none', 'Belum Didaftarkan')] + self.env['registrasi.produk']._fields['state']._description_selection(self.env),
        string='Status NIE', compute='_compute_registrasi_status', store=True)
    reg_halal_state = fields.Selection(
        selection=lambda self: [('none', 'Belum Didaftarkan')] + self.env['halal.registrasi']._fields['state']._description_selection(self.env),
        string='Status Halal', compute='_compute_registrasi_status', store=True)
    reg_nie_numbers = fields.Char(string='No. NIE', compute='_compute_registrasi_status', store=True)

    @api.model
    def _registrasi_pick(self, model, done_states, mou_ids):
        """Per MOU: pendaftaran yang sudah selesai diutamakan, selain itu yang terbaru."""
        picked = {}
        for rec in self.env[model].sudo().search([('mou_id', 'in', mou_ids)], order='id'):
            current = picked.get(rec.mou_id.id)
            if not current or rec.state in done_states or current.state not in done_states:
                picked[rec.mou_id.id] = rec
        return picked

    @api.depends(
        'brand_reg_ids.state', 'produk_reg_ids.state', 'halal_reg_ids.state',
        'produk_reg_ids.product_line_ids.nie_number',
    )
    def _compute_registrasi_status(self):
        ids = self.ids
        brands = self._registrasi_pick('registrasi.brand', ('approved',), ids)
        nies = self._registrasi_pick('registrasi.produk', ('nie_issued',), ids)
        halals = self._registrasi_pick('halal.registrasi', ('sertifikat_terbit',), ids)
        for mou in self:
            mou.reg_brand_state = brands[mou.id].state if mou.id in brands else 'none'
            mou.reg_nie_state = nies[mou.id].state if mou.id in nies else 'none'
            mou.reg_halal_state = halals[mou.id].state if mou.id in halals else 'none'
            numbers = nies[mou.id].product_line_ids.mapped('nie_number') if mou.id in nies else []
            mou.reg_nie_numbers = ', '.join(n for n in numbers if n)

    def write(self, vals):
        res = super().write(vals)

        doc_fields = [
            pair for pair in self.env['registrasi.brand']._MOU_DOC_FIELDS
            if vals.get(pair[0])
        ]
        if doc_fields:
            self._sync_docs_to_draft_brands(doc_fields)
        return res

    def _sync_docs_to_draft_brands(self, doc_fields):
        """Dokumen baru di MOU hanya ikut ke Brand Registrasi yang masih draft.
        Setelah keluar dari draft, dokumen diisi manual di Brand Registrasi."""
        brands = self.env['registrasi.brand'].sudo().search([
            ('mou_id', 'in', self.ids),
            ('state', '=', 'draft'),
        ])
        for brand in brands:
            mou = brand.mou_id.with_context(bin_size=False)
            brand.write({
                field: mou[field]
                for pair in doc_fields
                for field in pair
            })
