from odoo import models, fields, api

class MouContainer(models.Model):
    _name = 'mou.container'
    _description = 'Penampung Progress MOU'

    mou_id = fields.Many2one('draft.maklon', string='MOU', required=True, ondelete='cascade')
    pelanggan = fields.Many2one('res.partner', string='Pelanggan', related='mou_id.nama_cust', store=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id.id)

    # --- KOLOM REGISTRASI (biaya) ---
    reg_due_date = fields.Date(string='Reg. Due Date')
    reg_actual_date = fields.Date(string='Reg. Done Date')
    reg_nilai = fields.Monetary(string='Reg. Nilai', currency_field='currency_id')

    # --- KOLOM DP ---
    dp_due_date = fields.Date(string='DP Due Date')
    dp_actual_date = fields.Date(string='DP Done Date')
    dp_nilai = fields.Monetary(string='DP Nilai', currency_field='currency_id')

    # --- KOLOM NIE (progress dari nie.registrasi) ---
    nie_due_date = fields.Date(string='NIE Due Date')
    nie_actual_date = fields.Date(string='NIE Done Date')
    nie_nilai = fields.Monetary(string='NIE Nilai', currency_field='currency_id')
    nie_count = fields.Integer(string='Jumlah NIE', default=0)
    nie_done = fields.Integer(string='NIE Selesai', default=0)
    nie_progress = fields.Integer(string='NIE Progress (%)', default=0)
    nie_status = fields.Selection([
        ('start_reg', 'Start Registrasi'),
        ('revisi', 'Revisi'),
        ('ditolak', 'Ditolak'),
        ('teregistrasi', 'Teregistrasi'),
    ], string='NIE Status')

    # --- KOLOM HALAL (progress dari halal.registrasi) ---
    halal_due_date = fields.Date(string='Halal Due Date')
    halal_actual_date = fields.Date(string='Halal Done Date')
    halal_nilai = fields.Monetary(string='Halal Nilai', currency_field='currency_id')
    halal_count = fields.Integer(string='Jumlah Halal', default=0)
    halal_done = fields.Integer(string='Halal Selesai', default=0)
    halal_progress = fields.Integer(string='Halal Progress (%)', default=0)
    halal_status = fields.Selection([
        ('start_reg', 'Start Registrasi'),
        ('revisi', 'Revisi'),
        ('ditolak', 'Ditolak'),
        ('teregistrasi', 'Teregistrasi'),
    ], string='Halal Status')

    # --- KOLOM BRAND (progress dari brand.registrasi) ---
    brand_due_date = fields.Date(string='Brand Due Date')
    brand_actual_date = fields.Date(string='Brand Done Date')
    brand_nilai = fields.Monetary(string='Brand Nilai', currency_field='currency_id')
    brand_count = fields.Integer(string='Jumlah Brand', default=0)
    brand_done = fields.Integer(string='Brand Selesai', default=0)
    brand_progress = fields.Integer(string='Brand Progress (%)', default=0)
    brand_status = fields.Selection([
        ('start_reg', 'Start Registrasi'),
        ('revisi', 'Revisi'),
        ('ditolak', 'Ditolak'),
        ('teregistrasi', 'Teregistrasi'),
    ], string='Brand Status')

    # --- KOLOM PENGADAAN ---
    peng_due_date = fields.Date(string='Peng. Due Date')
    peng_actual_date = fields.Date(string='Peng. Done Date')
    peng_nilai = fields.Monetary(string='Peng. Nilai', currency_field='currency_id')

    # --- KOLOM BP (Balance Payment) ---
    bp_due_date = fields.Date(string='BP Due Date')
    bp_actual_date = fields.Date(string='BP Done Date')
    bp_nilai = fields.Monetary(string='BP Nilai', currency_field='currency_id')