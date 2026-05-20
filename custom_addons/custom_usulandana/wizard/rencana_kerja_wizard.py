from odoo import models, fields, api, exceptions
from datetime import timedelta


class RencanaKerjaWizardLine(models.TransientModel):
    _name = 'rencana.kerja.wizard.line'

    wizard_id = fields.Many2one(
        'rencana.kerja.wizard'
    )

    jenis_id = fields.Many2one(
        'jenis.rencana.kerja',
        string="Jenis"
    )

    tipe_visit_id = fields.Many2one(
        'tipe.visit',
        string="Tipe Visit"
    )

    tujuan_id = fields.Many2one(
        'tujuan.rencana.kerja',
        string="Tujuan"
    )

    deskripsi = fields.Text()
    tanggal = fields.Datetime(string="Tanggal")

class RencanaKerjaWizard(models.TransientModel):
    _name = 'rencana.kerja.wizard'

    line_ids = fields.One2many(
        'rencana.kerja.wizard.line',
        'wizard_id',
        string="Rencana Kerja"
    )

    def action_confirm(self):
        self.ensure_one()

        up_country = self.env['usulan.up.country'].browse(
            self.env.context.get('active_id')
        )

        if not up_country.tgl_depart or not up_country.tgl_pulang:
            raise exceptions.UserError(
                "Tanggal keberangkatan dan tanggal pulang harus diisi."
            )

        tanggal_wajib = []
        current_date = up_country.tgl_depart

        while current_date <= up_country.tgl_pulang:
            tanggal_wajib.append(current_date)
            current_date += timedelta(days=1)

        tanggal_rencana = set(
            line.tanggal.date()
            for line in self.line_ids
            if line.tanggal
        )
        tanggal_kurang = []

        for tanggal in tanggal_wajib:
            if tanggal not in tanggal_rencana:
                tanggal_kurang.append(
                    tanggal.strftime('%d-%m-%Y')
                )

        if tanggal_kurang:
            raise exceptions.UserError(
                "Rencana kerja belum lengkap.\n\n"
                "Tanggal berikut belum memiliki agenda:\n- "
                + "\n- ".join(tanggal_kurang)
            )

        # hapus data lama dulu supaya tidak duplicate
        up_country.rencana_kerja_line_ids.unlink()

        # create ulang dari wizard
        up_country.write({
            'rencana_kerja_line_ids': [
                (0, 0, {
                    'tanggal': l.tanggal,
                    'jenis_id': l.jenis_id.id,
                    'tipe_visit_id': l.tipe_visit_id.id,
                    'tujuan_id': l.tujuan_id.id,
                    'deskripsi': l.deskripsi,
                }) for l in self.line_ids
            ]
        })

        return {'type': 'ir.actions.act_window_close'}