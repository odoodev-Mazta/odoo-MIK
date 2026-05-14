from odoo import models,fields, api
from odoo.exceptions import UserError


class AkomodasiUcWizard(models.TransientModel):
    _name = 'akomodasi.uc.wizard'

    line_id = fields.Many2one('usulan.up.country.line')
    transportasi = fields.Selection(related='line_id.transportasi', readonly=False)

    dt_start = fields.Datetime("Waktu Berangkat / Check-in", required=True)
    dt_end = fields.Datetime("Waktu Pulang / Check-out")

    def action_confirm(self):
        self.ensure_one()

        if not self.line_id:
            raise UserError("Line tidak ditemukan.")

        self.line_id.write({
            'dt_start': self.dt_start,
            'dt_end': self.dt_end,
            'tgl_check_depart': self.dt_start.date() if self.dt_start else False,
        })

        self.line_id._compute_time_info_display()

        return {'type': 'ir.actions.act_window_close'}