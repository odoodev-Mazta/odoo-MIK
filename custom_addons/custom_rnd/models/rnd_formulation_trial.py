from odoo import fields, models

class RndFormulationTrial(models.Model):
    _name = "rnd.formulation.trial"
    _description = "Formula Trial"

    formulation_id = fields.Many2one(
        "rnd.formulation",
        required=True,
        ondelete="cascade"
    )

    version = fields.Char(
        string="Version",
        required=True
    )

    trial_date = fields.Date(
        string="Trial Date"
    )

    formula_description = fields.Text(
        string="Formula Composition"
    )

    test_result = fields.Text(
        string="Test Result"
    )

    conclusion = fields.Text(
        string="Conclusion"
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('testing', 'Testing'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='draft')

    test_summary = fields.Char(
        string="Test Summary"
    )

    attachment_ids = fields.Many2many(
        'ir.attachment',
        'rnd_trial_attachment_rel',
        'trial_id',
        'attachment_id',
        string='Attachments'
    )