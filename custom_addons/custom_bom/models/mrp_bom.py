from odoo import fields, models

from . import bom_excel

XLSX_MIMETYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    brand = fields.Char(
        string="Brand",
    )

    product_variant = fields.Char(
        string="Varian Produk",
    )

    jenis_produk_id = fields.Many2one("mrp.bom.jenis.produk", string="Jenis Produk")
    jenis_kemasan_id = fields.Many2one("mrp.bom.jenis.kemasan", string="Jenis Kemasan")

    # ------------------------------------------------------------------
    # Import / Export Excel
    # ------------------------------------------------------------------
    def _xlsx_download_action(self, filename, content):
        """Simpan file sebagai attachment sementara (diganti tiap kali) lalu unduh."""
        Attachment = self.env["ir.attachment"]
        Attachment.search([
            ("res_model", "=", "mrp.bom"),
            ("res_id", "=", 0),
            ("name", "=", filename),
            ("create_uid", "=", self.env.uid),
        ]).unlink()
        attachment = Attachment.create({
            "name": filename,
            "type": "binary",
            "raw": content,
            "mimetype": XLSX_MIMETYPE,
            "res_model": "mrp.bom",
            "res_id": 0,
        })
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }

    def action_import_bom(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Import BoM",
            "res_model": "mrp.bom.import.wizard",
            "view_mode": "form",
            "target": "new",
        }

    def action_download_import_format(self):
        content = bom_excel.build_workbook(
            bom_excel.SAMPLE_BOM_ROWS, bom_excel.SAMPLE_OP_ROWS, with_help=True,
        )
        return self._xlsx_download_action("format_import_bom.xlsx", content)

    def action_export_bom(self):
        """Export BoM yang dipilih di list; tanpa pilihan = semua BoM aktif."""
        boms = self or self.search([])
        bom_rows, op_rows = [], []
        for bom in boms:
            head = {
                "product_code": bom.product_id.default_code or bom.product_tmpl_id.default_code or "",
                "product_name": bom.product_tmpl_id.name,
                "product_qty": bom.product_qty,
                "bom_type": "kit" if bom.type == "phantom" else "normal",
                "bom_code": bom.code or "",
                "brand": bom.brand or "",
                "variant": bom.product_variant or "",
                "jenis_produk": bom.jenis_produk_id.name or "",
                "jenis_kemasan": bom.jenis_kemasan_id.name or "",
            }
            if not bom.bom_line_ids:
                bom_rows.append(dict(head))
            for line in bom.bom_line_ids:
                bom_rows.append({
                    **head,
                    "comp_code": line.product_id.default_code or "",
                    "comp_name": line.product_id.name,
                    "comp_qty": line.product_qty,
                    "comp_uom": line.product_uom_id.name,
                })
            for operation in bom.operation_ids.sorted("sequence"):
                op_rows.append({
                    "product_code": head["product_code"],
                    "bom_code": head["bom_code"],
                    "name": operation.name,
                    "workcenter": operation.workcenter_id.name,
                    "duration": operation.time_cycle_manual,
                    "sequence": operation.sequence,
                })
        content = bom_excel.build_workbook(bom_rows, op_rows)
        return self._xlsx_download_action("export_bom.xlsx", content)
