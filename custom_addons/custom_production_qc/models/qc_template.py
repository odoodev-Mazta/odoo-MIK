from odoo import models, fields


class QCTemplate(models.Model):
    _name = "production.qc.template"
    _description = "QC Template"

    name = fields.Char(
        required=True
    )

    qc_type = fields.Selection([
        ("incoming","Incoming QC"),
        ("process","Process QC"),
        ("final","Final QC"),
    ],
    default="process"
    )

    active = fields.Boolean(
        default=True
    )

    parameter_ids = fields.One2many(
        "production.qc.parameter",
        "template_id",
        string="Parameters"
    )

    operation_id = fields.Many2one(
        "mrp.routing.workcenter",
        string="Operation",
        required=True
    )