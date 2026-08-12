from odoo import models, fields, api
from odoo.exceptions import ValidationError

class QCSchedule(models.Model):
    _name = "production.qc.schedule"
    _description = "Production QC Schedule"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        string="QC Reference",
        default="New",
        tracking=True,
    )

    production_id = fields.Many2one(
        "mrp.production",
        string="Manufacturing Order",
        required=True,
        ondelete="cascade",
    )

    workorder_id = fields.Many2one(
        "mrp.workorder",
        string="Work Order",
        required=True,
        ondelete="cascade",
    )

    product_id = fields.Many2one(
        related="production_id.product_id",
        store=True,
        readonly=True,
    )

    operation_id = fields.Many2one(
        related="workorder_id.operation_id",
        store=True,
        readonly=True,
    )

    workcenter_id = fields.Many2one(
        related="workorder_id.workcenter_id",
        store=True,
        readonly=True,
    )

    workorder_state = fields.Selection(
        related="workorder_id.state",
        string="Work Order Status",
        store=True,
        readonly=True,
    )

    qc_template_id = fields.Many2one(
        "production.qc.template",
        string="QC Template",
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("waiting", "Waiting QC"),
            ("progress", "Checking"),
            ("done", "Passed"),
            ("failed", "Failed"),
        ],
        default="waiting",
        tracking=True,
    )

    check_line_ids = fields.One2many(
        "production.qc.check.line",
        "schedule_id",
        string="QC Checklist",
    )

    inspection_date = fields.Datetime(
        string="Inspection Date",
        readonly=True,
    )

    passed_count = fields.Integer(
        compute="_compute_qc_summary",
        string="Passed",
        readonly=True,
    )

    failed_count = fields.Integer(
        compute="_compute_qc_summary"
    )

    pending_count = fields.Integer(
        compute="_compute_qc_summary"
    )

    def _compute_qc_summary(self):

        for rec in self:
            rec.passed_count = len(
                rec.check_line_ids.filtered(
                    lambda x: x.status == "pass"
                )
            )

            rec.failed_count = len(
                rec.check_line_ids.filtered(
                    lambda x: x.status == "fail"
                )
            )

            rec.pending_count = len(
                rec.check_line_ids.filtered(
                    lambda x: x.status == "pending"
                )
            )

    def action_generate_checklist(self):

        for rec in self:

            if not rec.qc_template_id:
                raise ValidationError(
                    "Please select QC Template first."
                )

            if rec.check_line_ids:
                continue

            for parameter in rec.qc_template_id.parameter_ids:
                self.env[
                    "production.qc.check.line"
                ].create({
                    "schedule_id": rec.id,
                    "parameter_id": parameter.id,
                    "specification":parameter.specification,
                    "status": "pending",
                })

            rec.state = "waiting"

    def action_start(self):
        for rec in self:

            if not rec.check_line_ids:
                raise ValidationError(
                    "QC Checklist is empty."
                )

            rec.state = "progress"

    def action_check_all_result(self):
        for rec in self:

            for line in rec.check_line_ids:
                line.action_check_result()

        return True

    def action_done(self):

        for rec in self:

            rec.action_check_all_result()

            if not rec.check_line_ids:
                raise ValidationError(
                    "Please generate QC checklist first."
                )

            pending = rec.check_line_ids.filtered(
                lambda x: x.status == "pending"
            )

            if pending:
                raise ValidationError(
                    "Please complete all QC parameters first."
                )

            failed = rec.check_line_ids.filtered(
                lambda x: x.status == "fail"
            )

            if failed:
                rec.state = "failed"

            else:
                rec.state = "done"

            rec.inspection_date = fields.Datetime.now()

    def action_failed(self):
        for rec in self:
            rec.state = "failed"

    def action_reset(self):
        for rec in self:
            rec.state = "waiting"

            rec.check_line_ids.write({
                "status": "pending"
            })

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for rec in records:
            print(rec.qc_template_id)
            if rec.qc_template_id:
                rec.action_generate_checklist()

        return records


class DashboardTimeline(models.Model):
    """
    Inherit model dashboard.timeline.mou mengisi hook _get_qc_data() yang di custom_mou masih kosong.
    """
    _inherit = "dashboard.timeline.mou"

    def _get_qc_data(self, mou_id):
        schedules = self.env["production.qc.schedule"].search([
            ("production_id.production_plan_id.sale_order_id.mou_id", "=", mou_id),
        ])

        result = []
        for sched in schedules:
            result.append({
                "id": sched.id,
                "name": sched.name,
                "production": sched.production_id.name,
                "state": sched.state,
                "state_label": dict(
                    sched._fields["state"].selection
                ).get(sched.state, sched.state),
                "is_done": sched.state == "done",
                "is_failed": sched.state == "failed",
                "passed_count": sched.passed_count,
                "failed_count": sched.failed_count,
                "pending_count": sched.pending_count,
                "inspection_date": (
                    fields.Datetime.to_string(sched.inspection_date)
                    if sched.inspection_date else None
                ),
            })

        return result