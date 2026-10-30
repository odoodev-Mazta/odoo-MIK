from odoo import models,fields,api

class RndFormulation(models.Model):
    _name = 'rnd.formulation'
    _description = 'RnD Formulation'
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        string="Formulation Time",
        tracking=True,
    )

    customer_id = fields.Many2one(
        "res.partner",
        string="Customer"
    )

    responsible_id = fields.Many2one(
        "hr.employee",
        string="PIC R&D",
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('testing', 'Testing'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], compute="_compute_state", store=True)

    trial_line_ids = fields.One2many(
        "rnd.formulation.trial",
        "formulation_id",
        string="Formula Trials"
    )

    @api.depends("trial_line_ids.state")
    def _compute_state(self):
        for rec in self:
            lines = rec.trial_line_ids

            if not lines:
                rec.state = 'draft'
                continue

            statuses = lines.mapped('state')

            if any(x == 'rejected' for x in statuses):
                rec.state = 'rejected'
            elif all(x == 'approved' for x in statuses):
                rec.state = 'approved'
            elif any(x in ['testing', 'approved'] for x in statuses):
                rec.state = 'testing'
            else:
                rec.state = 'draft'