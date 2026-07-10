from odoo import fields, models


class RegistrasiProdukLine(models.Model):
    _name = 'registrasi.produk.line'
    _description = 'Registrasi Produk – Product Line Detail'
    _order = 'sequence, id'

    sequence = fields.Integer(
        string='Seq',
        default=10,
    )
    produk_id = fields.Many2one(
        comodel_name='registrasi.produk',
        string='Product Registration',
        required=True,
        ondelete='cascade',
        index=True,
    )

    # ─── Product Details ────────────────────────────────────────────────────
    product_name = fields.Char(
        string='Product Name',
        required=True,
    )
    description = fields.Selection(
        selection=[
            ('formula_import', 'Formula Import'),
            ('formula_lokal', 'Formula Lokal'),
        ],
        string='Formula Type',
        required=True,
    )
    netto = fields.Integer(
        string='Netto (g/ml)',
    )

    # ─── Packaging ──────────────────────────────────────────────────────────
    primary_packaging = fields.Selection(
        selection=[
            ('tube', 'Tube'),
            ('pot', 'Pot'),
            ('pump', 'Pump'),
            ('bottle', 'Bottle'),
            ('vial', 'Vial'),
            ('ampoule', 'Ampoule'),
            ('sachet', 'Sachet'),
        ],
        string='Primary Packaging',
    )
    secondary_packaging = fields.Selection(
        selection=[
            ('dus', 'Dus'),
            ('carton', 'Carton'),
        ],
        string='Secondary Packaging',
    )
    notes = fields.Text(
        string='Notes',
    )
