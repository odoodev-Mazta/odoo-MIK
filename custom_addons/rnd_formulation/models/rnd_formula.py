# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class RndFormula(models.Model):
    _name = 'rnd.formula'
    _description = 'Formulasi Utama RnD'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Kode Formulasi', 
        required=True, 
        copy=False, 
        readonly=True, 
        default=lambda self: _('New')
    )
    product_target_name = fields.Char(
        string='Nama Target Produk', 
        required=True, 
        tracking=True
    )
    target_qty = fields.Float(
        string='Target Takaran Total (C)', 
        required=True, 
        tracking=True
    )
    uom_id = fields.Many2one(
        'uom.uom', 
        string='Satuan Ukur (UoM)', 
        required=True
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'Dalam Pengujian'),
        ('done', 'Selesai / Pas'),
        ('cancel', 'Dibatalkan')
    ], string='Status', default='draft', tracking=True)

    trial_ids = fields.One2many(
        'rnd.formula.trial', 
        'formula_id', 
        string='Daftar Percobaan / Trial'
    )

    result_status = fields.Selection([
        ('under', 'Belum Pas (Kurang)'),
        ('pass', 'PAS'),
        ('over', 'Kelebihan')
    ], string='Status Hasil Pengujian', compute='_compute_latest_result_status', store=True)

    trial_count = fields.Integer(
        string='Jumlah Trial', 
        compute='_compute_trial_count', 
        store=True
    )
    
    @api.depends('trial_ids')
    def _compute_trial_count(self):
        for record in self:
            record.trial_count = len(record.trial_ids)

    # PERBAIKAN DECORATOR DI SINI
    @api.depends('trial_ids', 'trial_ids.result_status')
    def _compute_latest_result_status(self):
        for record in self:
            if not record.trial_ids:
                record.result_status = 'under'
            else:
                # Ambil status dari trial dengan nomor trial paling tinggi
                last_trial = record.trial_ids.sorted(key=lambda t: t.trial_number, reverse=True)[0]
                record.result_status = last_trial.result_status

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('rnd.formula') or _('New')
        return super().create(vals_list)

    def action_set_in_progress(self):
        self.write({'state': 'in_progress'})

    def action_set_done(self):
        for record in self:
            if record.result_status != 'pass':
                raise UserError("Hasil pengujian belum PAS (Sesuai)! Tidak dapat menandai selesai.")
            record.state = 'done'

    def action_set_draft(self):
        self.write({'state': 'draft'})


class RndFormulaTrial(models.Model):
    _name = 'rnd.formula.trial'
    _description = 'Percobaan Trial Formulasi'
    _order = 'trial_number asc'

    formula_id = fields.Many2one(
        'rnd.formula', 
        string='Formulasi Utama', 
        ondelete='cascade'
    )
    trial_number = fields.Integer(string='Trial Ke-', default=1)
    line_ids = fields.One2many(
        'rnd.formula.trial.line', 
        'trial_id', 
        string='Bahan / Takaran'
    )
    total_qty = fields.Float(
        string='Total Takaran Hasil', 
        compute='_compute_total_qty', 
        store=True
    )
    target_qty = fields.Float(
        related='formula_id.target_qty', 
        string='Target Takaran'
    )
    result_status = fields.Selection([
        ('under', 'Belum Pas (Kurang)'),
        ('pass', 'PAS'),
        ('over', 'Kelebihan')
    ], string='Hasil Pengujian', compute='_compute_result_status', store=True)
    notes = fields.Text(string='Catatan Lab / Hasil Evaluasi')

    @api.depends('line_ids.qty')
    def _compute_total_qty(self):
        for trial in self:
            trial.total_qty = sum(line.qty for line in trial.line_ids)

    @api.depends('total_qty', 'target_qty')
    def _compute_result_status(self):
        for trial in self:
            if trial.target_qty > 0 and trial.total_qty == trial.target_qty:
                trial.result_status = 'pass'
            elif trial.total_qty < trial.target_qty:
                trial.result_status = 'under'
            else:
                trial.result_status = 'over'

    def action_duplicate_trial(self):
        self.ensure_one()
        next_number = len(self.formula_id.trial_ids) + 1
        
        self.create({
            'formula_id': self.formula_id.id,
            'trial_number': next_number,
            'notes': f"Hasil turunan dari Trial #{self.trial_number}",
            'line_ids': [(0, 0, {
                'ingredient_name': line.ingredient_name,
                'qty': line.qty,
            }) for line in self.line_ids]
        })
        return True


class RndFormulaTrialLine(models.Model):
    _name = 'rnd.formula.trial.line'
    _description = 'Detail Bahan Input Trial'

    trial_id = fields.Many2one('rnd.formula.trial', ondelete='cascade')
    ingredient_name = fields.Char(string='Nama Bahan (A/B/dst)', required=True)
    qty = fields.Float(string='Takaran / Jumlah', required=True)