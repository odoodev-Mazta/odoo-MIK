from odoo import _, fields, models
from odoo.exceptions import UserError


class DraftMaklon(models.Model):
    _inherit = 'draft.maklon'

    project_ids = fields.One2many('project.project', 'mou_id', string="Project")
    project_count = fields.Integer(compute='_compute_project_count')

    def _compute_project_count(self):
        for rec in self:
            rec.project_count = len(rec.project_ids)

    def _ensure_project(self):
        """Satu Project per MOU. Project lama (versi sebelumnya: satu per SO) digabung ke satu, sisanya diarsipkan."""
        self.ensure_one()
        Project = self.env['project.project'].with_context(active_test=False)
        projects = Project.search([('mou_id', '=', self.id)], order='id')
        if projects:
            project = projects[0]
            (projects - project).write({'active': False})
            if not project.active:
                project.active = True
            return project
        return Project.create({
            'name': '%s - %s' % (self.draft_name or _('MOU'), self.brand or self.nama_cust.name or ''),
            'partner_id': self.nama_cust.id,
            'mou_id': self.id,
        })

    def action_open_project(self):
        """Buat / sinkronkan Project MOU ini, lalu buka daftar task-nya. Pilih SO lewat dropdown 'Per SO' di kotak
        pencarian: yang tampil seluruh alur SO itu (tahap MOU + dokumen SO itu). Terbuka langsung di SO terbaru."""
        self.ensure_one()
        if self.state != 'mou':
            raise UserError(_("Project hanya bisa dibuat untuk MOU yang sudah dikonfirmasi."))
        project = self._ensure_project()
        project._sync_from_mou()
        return project.action_view_tasks()
