from odoo import fields, models, api

class ProductionMachineCapacity(models.Model):
    _name = "mrp.production.machine.capacity"
    _description = "Machine Capacity"
    _order = "machine_id, packaging_type, package_size"

    machine_id = fields.Many2one(
        "mrp.production.machine",
        required=True,
        ondelete="cascade",
    )

    packaging_type = fields.Selection(
        [
            ("tube", "Tube"),
            ("jar", "Jar"),
            ("bottle", "Bottle"),
            ("sachet", "Sachet"),
        ],
        required=True,
    )

    package_size = fields.Float(
        string="Package Size",
        required=True,
    )

    package_uom = fields.Selection(
        [
            ("gr", "Gram"),
            ("ml", "mL"),
        ],
        default="gr",
        required=True,
    )

    capacity_per_day = fields.Float(
        string="Capacity / Day",
        required=True,
    )

    uom_id = fields.Many2one(
        "uom.uom",
        string="Production Unit",
    )

    note = fields.Char()

    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
    )

    @api.depends(
        "machine_id",
        "packaging_type",
        "package_size",
        "package_uom",
    )
    def _compute_display_name(self):
        package_dict = dict(
            self._fields["packaging_type"].selection
        )

        uom_dict = dict(
            self._fields["package_uom"].selection
        )

        for rec in self:
            package = package_dict.get(rec.packaging_type, "")

            uom = uom_dict.get(rec.package_uom, "")

            rec.display_name = (
                f"{rec.machine_id.name} - "
                f"{package} "
                f"{rec.package_size:g} "
                f"{uom}"
            )