from odoo import _, api, fields, models
from odoo.exceptions import UserError


class DesignFilePreview(models.TransientModel):
    """Popup untuk melihat file Usulan / Approval Design dulu, unduh lewat tombol bila perlu."""
    _name = 'design.file.preview'
    _description = 'Preview File Design'

    res_model = fields.Char(required=True, readonly=True)
    res_id = fields.Integer(required=True, readonly=True)
    res_field = fields.Char(required=True, readonly=True)
    name = fields.Char(string='Nama File', readonly=True)
    kind = fields.Selection([('pdf', 'PDF'), ('image', 'Gambar'), ('other', 'Lainnya')], readonly=True)
    file = fields.Binary(compute='_compute_file', string='File')
    image = fields.Binary(compute='_compute_file', string='Gambar')

    def _source(self):
        """Record asal, setelah dipastikan user boleh membacanya dan fieldnya memang file design."""
        self.ensure_one()
        allowed = {('design.usulan', 'attachment_design'), ('design.usulan.line', 'attachment'),
                   ('design.approval', 'attachment_form')}
        if (self.res_model, self.res_field) not in allowed:
            raise UserError(_("File tidak dikenal."))
        record = self.env[self.res_model].browse(self.res_id)
        record.check_access('read')
        return record

    @api.depends('res_model', 'res_id', 'res_field')
    def _compute_file(self):
        for preview in self:
            data = preview._source().with_context(bin_size=False)[preview.res_field]
            preview.file = data
            preview.image = data

    @api.model
    def open_for(self, record, field_name, filename):
        record.ensure_one()
        record.check_access('read')
        if not record[field_name]:
            raise UserError(_("Belum ada file yang diunggah."))
        attachment = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', record._name), ('res_id', '=', record.id), ('res_field', '=', field_name)], limit=1)
        mimetype = attachment.mimetype or ''
        extension = (filename or '').lower().rsplit('.', 1)[-1]
        if 'pdf' in mimetype or extension == 'pdf':
            kind = 'pdf'
        elif mimetype.startswith('image/') or extension in ('png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg'):
            kind = 'image'
        else:
            kind = 'other'
        preview = self.create({
            'res_model': record._name, 'res_id': record.id, 'res_field': field_name,
            'name': filename or _('File Design'), 'kind': kind,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': preview.name,
            'res_model': self._name,
            'res_id': preview.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'dialog_size': 'extra-large'},
        }

    def action_download(self):
        self._source()
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s/%s/%s?download=true&filename_field=%s_fname' % (
                self.res_model, self.res_id, self.res_field, self.res_field),
            'target': 'self',
        }
