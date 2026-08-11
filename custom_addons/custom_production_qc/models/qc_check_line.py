from odoo import fields, models

class QCCheckLine(models.Model):
    _name = "production.qc.check.line"
    _description = "QC Check Result"

    schedule_id = fields.Many2one(
        "production.qc.schedule",
        required=True,
        ondelete="cascade"
    )

    qc_state = fields.Selection(
        related="schedule_id.state",
        store=False,
    )

    parameter_id = fields.Many2one(
        "production.qc.parameter",
        required=True
    )

    specification = fields.Char(
        related="parameter_id.specification",
        store=True,
        string="Specification"
    )

    min_value = fields.Float(
        related="parameter_id.min_value",
        store=True,
        string="Min Value"
    )

    max_value = fields.Float(
        related="parameter_id.max_value",
        store=True,
        string="Max Value"
    )

    actual_value = fields.Char(
        string="Actual Value"
    )

    result = fields.Char(
        string="Result Description",
    )

    status = fields.Selection(
        [
            ("pending", "Pending"),
            ("pass", "Pass"),
            ("fail", "Fail"),
        ],
        string="Status",
        default="pending",
    )

    remark = fields.Text(
        string="Remark"
    )


    def action_check_result(self):
        for rec in self:
            parameter = rec.parameter_id

            # belum ada input
            if not rec.actual_value:
                rec.status = "pending"
                rec.result = "No value entered"
                continue

            # Numeric parameter
            if parameter.parameter_type == "numeric":
                try:
                    value = float(rec.actual_value)
                except ValueError:
                    rec.status = "fail"
                    rec.result = "Invalid numeric value"
                    continue

                failed = False

                if parameter.min_value is not False:
                    if value < parameter.min_value:
                        failed = True

                if parameter.max_value is not False:
                    if value > parameter.max_value:
                        failed = True

                if failed:
                    rec.status = "fail"
                    rec.result = (
                        f"Value {value} outside specification"
                    )
                else:
                    rec.status = "pass"
                    rec.result = (
                        f"Value {value} within specification"
                    )

            # Text / manual checking
            else:
                rec.status = "pass"
                rec.result = (
                    "Manual verification completed"
                )

        return True