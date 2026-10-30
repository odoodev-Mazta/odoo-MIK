from odoo import models,fields,api

class DesignUsulan(models.Model):
    _name = 'design.usulan'
    _description = 'Usulan Design'

    date = fields.Date(string='Tgl', default=fields.Date.context_today)
    partner_id = fields.Many2one('res.partner', string='Pelanggan')
    brand = fields.Char(string='Brand')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('progress', 'In Progress'),
        ('done', 'Selesai')
    ], string='Status', default='draft')
    attachment = fields.Binary(string='Attachment')
    is_ontime = fields.Boolean(string='Ontime', default=True)

    @api.model
    def get_dashboard_data(self):
        # Perhitungan Progress
        total_usulan = self.search_count([])
        selesai_usulan = self.search_count([('state', '=', 'done')])
        progress_pct = (selesai_usulan / total_usulan * 100) if total_usulan > 0 else 0

        # Perhitungan Ontime/Overdue (dari yang sudah selesai)
        ontime_count = self.search_count([('state', '=', 'done'), ('is_ontime', '=', True)])
        ontime_pct = (ontime_count / selesai_usulan * 100) if selesai_usulan > 0 else 0

        return {
            'total': total_usulan,
            'done': selesai_usulan,
            'progress_pct': round(progress_pct, 1),
            'ontime': ontime_count,
            'ontime_pct': round(ontime_pct, 1),
        }