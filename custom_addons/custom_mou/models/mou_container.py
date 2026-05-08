from odoo import models,fields,api

class MouContainer(models.Model):
    _name = 'mou.container'
    _description = 'Penampung Progress MOU'

    mou_id = fields.Many2one('draft.maklon', string='MOU', required=True, ondelete='cascade')
    pelanggan = fields.Many2one('res.partner', string='Pelanggan', related='mou_id.nama_cust', store=True)

    # x

    # --- KOLOM REGISTRASI ---
    reg_due_date = fields.Date(string='Reg. Due Date')
    reg_actual_date = fields.Date(string='Reg. Done Date')
    reg_nilai = fields.Monetary(string='Reg. Nilai', currency_field='currency_id')

    # --- KOLOM DP ---
    dp_due_date = fields.Date(string='DP Due Date')
    dp_actual_date = fields.Date(string='DP Done Date')
    dp_nilai = fields.Monetary(string='DP Nilai', currency_field='currency_id')

    # --- KOLOM NIE ---
    nie_due_date = fields.Date(string='NIE Due Date')
    nie_actual_date = fields.Date(string='NIE Done Date')
    nie_nilai = fields.Monetary(string='NIE Nilai', currency_field='currency_id')

    # --- KOLOM PENGADAAN ---
    peng_due_date = fields.Date(string='Peng. Due Date')
    peng_actual_date = fields.Date(string='Peng. Done Date')
    peng_nilai = fields.Monetary(string='Peng. Nilai', currency_field='currency_id')

    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id.id)