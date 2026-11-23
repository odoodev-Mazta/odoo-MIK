import re

from odoo import Command, api, fields, models

SIZE_PATTERN = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:gr|gram|g|ml)\b", re.IGNORECASE)


def product_fill_size(product):
    """Isi per pcs dari nama produk, mis. 'CAMEA CLARIFYING 20 GR' -> 20.0. 0 bila tidak ketemu."""
    match = SIZE_PATTERN.search(product.name or "") if product else None
    return float(match.group(1).replace(",", ".")) if match else 0.0


class QCTemplate(models.Model):
    _inherit = "production.qc.template"

    # Template untuk tahap Plan Produksi tidak memakai Operation.
    operation_id = fields.Many2one(required=False)
    stage_id = fields.Many2one(
        "mrp.production.stage", string="Tahap Proses",
        help="Template ini dipakai saat tahap ini dimulai di Plan Produksi.",
    )
    fill_size = fields.Float(
        string="Isi per pcs (gr/ml)",
        help="Mis. 20 untuk produk 20 gr, 50 untuk produk 50 gr. Dicocokkan dengan angka gr/ml di nama produk. "
             "Kosongkan (0) untuk template umum tahap ini.",
    )
    product_tmpl_ids = fields.Many2many(
        "product.template", "production_qc_template_product_rel", "template_id", "product_tmpl_id",
        string="Khusus Produk",
        help="Isi bila template ini hanya untuk produk tertentu. Paling diutamakan.",
    )

    def _match_level(self, product):
        """3 = produk disebut khusus, 2 = isi per pcs cocok, 1 = template umum, 0 = tidak cocok."""
        self.ensure_one()
        if self.product_tmpl_ids:
            return 3 if product.product_tmpl_id in self.product_tmpl_ids else 0
        if self.fill_size:
            size = product_fill_size(product)
            return 2 if size and abs(size - self.fill_size) < 1e-6 else 0
        return 1

    @api.model
    def _find_for_stage(self, stage_master, product):
        templates = self.search([("stage_id", "=", stage_master.id)])
        best, level = self.browse(), 0
        for template in templates:
            current = template._match_level(product)
            if current > level:
                best, level = template, current
        return best


class ProductionStage(models.Model):
    _inherit = "mrp.production.stage"

    qc_template_ids = fields.One2many("production.qc.template", "stage_id", string="QC Template")

    @api.model
    def _move_parameters_to_qc_templates(self):
        """Sekali saja: parameter yang dulu diisi di master tahap dipindah jadi QC Template umum tahap itu."""
        params = self.env["ir.config_parameter"].sudo()
        key = "custom_production_qc.stage_parameters_moved"
        if params.get_param(key):
            return
        Uom = self.env["uom.uom"]
        for stage in self.with_context(active_test=False).search([("parameter_ids", "!=", False)]):
            if stage.qc_template_ids:
                continue
            lines = []
            for parameter in stage.parameter_ids:
                unit = (parameter.unit or "").strip()
                uom = Uom
                if unit:
                    uom = Uom.search([("name", "=ilike", "g" if unit.lower() in ("gr", "gram") else unit)], limit=1)
                lines.append((0, 0, {
                    "sequence": parameter.sequence,
                    "name": parameter.name,
                    "specification": parameter.specification,
                    "parameter_type": parameter.parameter_type,
                    "uom_id": uom.id,
                    "min_value": parameter.min_value,
                    "max_value": parameter.max_value,
                    "required": parameter.required,
                }))
            self.env["production.qc.template"].create({
                "name": f"QC {stage.name} (umum)",
                "qc_type": "process",
                "stage_id": stage.id,
                "parameter_ids": lines,
            })
        params.set_param(key, "1")

    # Parameter pemeriksaan standar dari tim QC. Batas min/maks sengaja kosong (0 = tanpa batas):
    # isi di QC Template sesuai spesifikasi tiap produk.
    STANDARD_QC_PARAMETERS = {
        "stage_mixing": [
            ("Viskositas", "number"),
            ("pH", "number"),
            ("Bobot Jenis", "number"),
        ],
        "stage_filling": [
            ("Viskositas", "number"),
            ("pH", "number"),
            ("Bobot Jenis", "number"),
            ("Waktu Koagulasi", "number"),
            ("Tidak Ada Kebocoran", "boolean"),
        ],
        "stage_packing": [
            ("Kesesuaian Nomor Batch", "boolean"),
            ("Kesesuaian Hasil / Isi Produk", "boolean"),
        ],
    }

    @api.model
    def _seed_standard_qc_parameters(self):
        """Sekali saja: tambahkan parameter standar QC ke template umum tiap tahap (dibuat bila belum ada)."""
        params = self.env["ir.config_parameter"].sudo()
        key = "custom_production_qc.standard_parameters_seeded"
        if params.get_param(key):
            return
        Template = self.env["production.qc.template"]
        for xmlid, definitions in self.STANDARD_QC_PARAMETERS.items():
            stage = self.env.ref(f"custom_production_planning.{xmlid}", raise_if_not_found=False)
            if not stage:
                continue
            template = Template.search([
                ("stage_id", "=", stage.id), ("product_tmpl_ids", "=", False), ("fill_size", "=", 0),
            ], limit=1)
            if not template:
                template = Template.create({
                    "name": f"QC {stage.name} (umum)", "qc_type": "process", "stage_id": stage.id,
                })
            existing = {name.lower() for name in template.parameter_ids.mapped("name")}
            sequence = max(template.parameter_ids.mapped("sequence") or [0])
            lines = []
            for name, parameter_type in definitions:
                if name.lower() in existing:
                    continue
                sequence += 10
                lines.append((0, 0, {
                    "sequence": sequence, "name": name, "parameter_type": parameter_type, "required": True,
                }))
            if lines:
                template.write({"parameter_ids": lines})
        params.set_param(key, "1")


class ProductionPlanStage(models.Model):
    _inherit = "mrp.production.plan.stage"

    qc_template_id = fields.Many2one(
        "production.qc.template", string="QC Template Dipakai", copy=False,
        domain="[('stage_id', '=', stage_id)]",
        help="Dipilih otomatis saat tahap dimulai. Bisa diganti saat Menunggu QC; parameter pemeriksaan ikut diganti.",
    )

    @staticmethod
    def _template_parameter_vals(template):
        return [{
            "sequence": parameter.sequence,
            "name": parameter.name,
            "specification": parameter.specification,
            "parameter_type": parameter.parameter_type,
            "unit": parameter.uom_id.name or False,
            "min_value": parameter.min_value,
            "max_value": parameter.max_value,
            "required": parameter.required,
        } for parameter in template.parameter_ids]

    def _get_qc_parameter_vals(self):
        self.ensure_one()
        template = self.env["production.qc.template"]._find_for_stage(self.stage_id, self.product_id)
        self.with_context(skip_qc_template_reload=True).qc_template_id = template
        if not template:
            return super()._get_qc_parameter_vals()
        return self._template_parameter_vals(template)

    @api.onchange("qc_template_id")
    def _onchange_qc_template_id(self):
        """Ganti template di form pemeriksaan: parameter langsung diganti (nilai aktual dikosongkan)."""
        for stage in self:
            if stage.state == "waiting_qc" and stage.qc_template_id:
                stage.check_ids = [Command.clear()] + [
                    Command.create(vals) for vals in self._template_parameter_vals(stage.qc_template_id)
                ]

    def write(self, vals):
        result = super().write(vals)
        # Diganti di luar form (tanpa check_ids ikut dikirim): muat ulang parameternya di server.
        if "qc_template_id" in vals and "check_ids" not in vals and not self.env.context.get("skip_qc_template_reload"):
            for stage in self.filtered(lambda s: s.state == "waiting_qc" and s.qc_template_id):
                stage.check_ids.unlink()
                stage.check_ids = [Command.create(v) for v in self._template_parameter_vals(stage.qc_template_id)]
        if "qc_template_id" in vals and not self.env.context.get("skip_qc_template_reload"):
            for stage in self:
                stage.plan_id.message_post(
                    body=f"QC Template {stage._label()} diganti ke {stage.qc_template_id.name or '-'} oleh {self.env.user.name}.",
                    subtype_xmlid="mail.mt_note",
                )
        return result
