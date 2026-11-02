from odoo import models


class DraftMaklon(models.Model):
    _inherit = 'draft.maklon'

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
