from odoo import models,fields,api

class EcatalogueProduct(models.Model):
    _name = 'ecatalogue.product'
    _description = 'E-Catalogue Marketing Product'

    product_id = fields.Many2one('product.product', string="Master Product", required=True)
    name = fields.Char(string="Product Name", related='product_id.name',readonly=False)
    image_1920 = fields.Image(string="Image", max_width=1920, max_height=1920, store=True)
    image_512 = fields.Image(string="Image 512", related='image_1920', max_width=512, max_height=512, store=True)
    price = fields.Float(string="HNA (Rp)")
    manfaat = fields.Text(string="Manfaat")
    kandungan = fields.Text(string="Kandungan")
    ukuran_ecatalogue = fields.Float(string="Ukuran (Gr)", readonly=False)
    moq_ecatalogue = fields.Float(string="MOQ", readonly=False)
    total_maklon = fields.Integer(string="Total Maklon (Rp)", readonly=False)
    jenis_kemasan = fields.Char(string="Jenis Kemasan", readonly=False)
    berat_bersih = fields.Char(string="Nett", readonly=False)
    # masa produksi bakal pake compute keknya
    masa_produksi = fields.Integer(string="Masa Produksi (hari kerja)", readonly=False)
    # terhitung berapa hari sejak dp dibayarkan (notes kecil)
