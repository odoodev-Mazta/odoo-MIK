from odoo import _, api, fields, models
from odoo.exceptions import UserError


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def action_preview_halal_cert(self):
        """Tombol 'Lihat' pada daftar sertifikat halal: tampilkan dulu di popup, unduh bila perlu."""
        self.ensure_one()
        self.check_access('read')
        preview = self.env['registrasi.halal.cert.preview'].create({'attachment_id': self.id})
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': preview._name,
            'res_id': preview.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'dialog_size': 'extra-large'},
        }


class HalalCertWizard(models.TransientModel):
    _name = 'registrasi.halal.cert.wizard'
    _description = 'Upload Sertifikat Halal'

    produk_id = fields.Many2one('registrasi.produk', string='Registrasi Produk', required=True, readonly=True)
    attachment_ids = fields.Many2many(
        'ir.attachment', 'registrasi_halal_cert_wizard_rel', 'wizard_id', 'attachment_id',
        string='File Sertifikat')

    def action_upload(self):
        self.ensure_one()
        if not self.attachment_ids:
            raise UserError(_("Pilih minimal satu file sertifikat halal."))
        self.produk_id.check_access('write')
        # Pindahkan file dari wizard ke Registrasi Produk supaya hak aksesnya mengikuti record itu.
        self.attachment_ids.sudo().write({'res_model': 'registrasi.produk', 'res_id': self.produk_id.id})
        self.produk_id.write({'halal_cert_ids': [(4, attachment.id) for attachment in self.attachment_ids]})
        return {'type': 'ir.actions.act_window_close'}


class HalalCertPreview(models.TransientModel):
    _name = 'registrasi.halal.cert.preview'
    _description = 'Preview Sertifikat Halal'

    attachment_id = fields.Many2one('ir.attachment', required=True, readonly=True, ondelete='cascade')
    name = fields.Char(related='attachment_id.name', string='Nama File')
    file = fields.Binary(related='attachment_id.datas', string='File')
    image = fields.Binary(related='attachment_id.datas', string='Gambar')
    kind = fields.Selection(
        [('pdf', 'PDF'), ('image', 'Gambar'), ('other', 'Lainnya')], compute='_compute_kind')

    @api.depends('attachment_id')
    def _compute_kind(self):
        for preview in self:
            mimetype = preview.attachment_id.mimetype or ''
            preview.kind = 'pdf' if 'pdf' in mimetype else 'image' if mimetype.startswith('image/') else 'other'

    def action_download(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % self.attachment_id.id,
            'target': 'self',
        }
