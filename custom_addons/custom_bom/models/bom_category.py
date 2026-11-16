from odoo import fields, models


class MrpBomJenisProduk(models.Model):
    _name = "mrp.bom.jenis.produk"
    _description = "Jenis Produk BoM"
    _order = "name"

    name = fields.Char(string="Jenis Produk", required=True)

    _name_unique = models.Constraint("unique(name)", "Jenis Produk ini sudah ada.")


class MrpBomJenisKemasan(models.Model):
    _name = "mrp.bom.jenis.kemasan"
    _description = "Jenis Kemasan BoM"
    _order = "name"

    name = fields.Char(string="Jenis Kemasan", required=True)

    _name_unique = models.Constraint("unique(name)", "Jenis Kemasan ini sudah ada.")
