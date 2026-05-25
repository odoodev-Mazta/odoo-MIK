from odoo import models, fields, api

class UsulanPlanPaymentCalendarWizard(models.TransientModel):
    _name = 'usulan.plan.payment.calendar.wizard'
    _description = 'Calendar Plan Payment Popup'

    selected_date = fields.Date(string='Tanggal')

    # line_ids = fields.One2many(
    #     'usulan.plan.payment.calendar.wizard.line',
    #     'wizard_id',
    #     string='Plan Payment'
    # )

    selected_date = fields.Date()

    schedule_ids = fields.Many2many(
        'usulan.payment.schedule',
        string='Schedules'
    )

    department_summary_html = fields.Html(
        string='Department Summary',
        compute='_compute_department_summary'
    )

    # @api.model
    # def get_schedule_by_date(self, full_date, year, month):
    #     schedules = self.env['usulan.payment.schedule'].search([
    #         ('plan_payment_date', '=', full_date)
    #     ])
    #
    #     lines = []
    #     for s in schedules:
    #         lines.append((0, 0, {
    #             'department_id': s.plan_payment_id.department_id.id,
    #             'tgl_usulan': s.plan_payment_id.usulan_dana_id.tgl_usulan if s.plan_payment_id.usulan_dana_id else False,
    #             'due_date': s.date_payment,
    #             'description': s.plan_payment_id.description,
    #             'amount': s.amount,
    #             'state': s.state,
    #             'plan_payment_id': s.plan_payment_id.id,
    #         }))
    #
    #     return {'lines': lines}

    # def action_save_changes(self):
    #     for wizard in self:
    #         for schedule in wizard.schedule_ids:
    #             schedule.write({
    #                 'plan_payment_date': schedule.plan_payment_date
    #             })
    #
    #     return {'type': 'ir.actions.act_window_close'}

    def action_save_changes(self):
        self.ensure_one()

        for schedule in self.schedule_ids:
            schedule.with_context(from_reschedule_wizard=True).write({
                'plan_payment_date': schedule.plan_payment_date
            })

        return {'type': 'ir.actions.act_window_close'}

    @api.depends('schedule_ids')
    def _compute_department_summary(self):

        for rec in self:

            html = ""

            departments = {}

            for schedule in rec.schedule_ids:

                dept = schedule.department_id

                if dept.id not in departments:
                    departments[dept.id] = {
                        'name': dept.name,
                        'total': 0,
                    }

                departments[dept.id]['total'] += schedule.amount

            for dept_data in departments.values():
                budget = 100000000

                percentage = (
                        dept_data['total'] / budget * 100
                ) if budget else 0

                color = 'red' if percentage > 100 else 'green'

                html += f"""
                    <div style="padding:10px;margin-bottom:8px;border-radius:8px;background:#f5f5f5;">
                        <b>{dept_data['name']}</b><br/>
                        <span style="color:{color};font-weight:bold;">
                            {percentage:.2f}%
                        </span>
                    </div>
                """
            rec.department_summary_html = html

class UsulanPlanPaymentCalendarWizardLine(models.TransientModel):
    _name = 'usulan.plan.payment.calendar.wizard.line'
    _description = 'Calendar Plan Payment Popup Line'

    wizard_id = fields.Many2one(
        'usulan.plan.payment.calendar.wizard'
    )

    department_id = fields.Many2one(
        'hr.department',
        string='Departemen'
    )

    tgl_usulan = fields.Date(
        string='Tgl Usulan'
    )

    due_date = fields.Date(
        string='Due Date'
    )

    description = fields.Char(
        string='Keterangan'
    )

    amount = fields.Monetary(
        string='Nominal'
    )

    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )

    plan_payment_id = fields.Many2one(
        'usulan.plan.payment',
        string='Plan Payment'
    )

    state = fields.Selection([
        ('menggantung', 'Menggantung'),
        ('plan_payment', 'Plan Payment'),
        ('reschedule', 'Reschedule'),
        ('rilis', 'Rilis'),
        ('cancel', 'Cancel')
    ])

    def action_open_plan_payment(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'usulan.plan.payment',
            'res_id': self.plan_payment_id.id,
            'view_mode': 'form',
            'target': 'current',
        }