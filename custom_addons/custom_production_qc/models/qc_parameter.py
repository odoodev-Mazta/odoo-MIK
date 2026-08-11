from odoo import fields, models

class QCParameter(models.Model):
    _name = "production.qc.parameter"
    _description = "QC Parameter"
    _order = "sequence,id"

    sequence = fields.Integer(
        default=10
    )

    template_id = fields.Many2one(
        "production.qc.template",
        required=True,
        ondelete="cascade"
    )

    name = fields.Char(
        required=True
    )

    specification = fields.Char()

    parameter_type = fields.Selection(
        [
            ("number", "Number"),
            ("text", "Text"),
            ("boolean", "Yes / No"),
        ],
        default="number",
        required=True,
    )

    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit"
    )

    min_value = fields.Float(
        string="Minimum Value"
    )

    max_value = fields.Float(
        string="Maximum Value"
    )

    required = fields.Boolean(
        default=True
    )