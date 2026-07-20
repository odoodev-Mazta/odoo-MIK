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
            ('botol', 'Botol'),
            ('vial', 'Vial'),
            ('ampoule', 'Ampoule'),
            ('sachet', 'Sachet'),
            ('jar', 'Jar'),
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
    # product_name = fields.Char(
    #     string='Product Name (Request)',
    #     required=True,
    #     tracking=True,
    # )
    official_product_name = fields.Char(
        string='Official Product Name (RO Drafted)',
        tracking=True,
        copy=False,
    )
    product_name_revision_count = fields.Integer(
        string='Product Name Revision Count',
        default=0,
        copy=False,
        tracking=True,
    )
    confirmation_counter = fields.Integer(
        string='BPOM Confirmation Counter',
        default=0,
        copy=False,
        tracking=True,
    )

    nie_number = fields.Char(
        string='NIE Number',
        copy=False,
        tracking=True,
    )
    nie_issued_date = fields.Date(
        string='NIE Issued Date',
        copy=False,
        tracking=True,
    )
    nie_expired_date = fields.Date(
        string='NIE Expired Date',
        copy=False,
        tracking=True,
    )
    product_template_id = fields.Many2one(
        comodel_name='product.template',
        string='Product',
        copy=False,
        tracking=True,
    )

    def _create_or_link_product_template(self):
        self.ensure_one()

        Product = self.env['product.template']

        existing = Product.search(
            [
                ('default_code', '=', self.nie_number)
            ],
            limit=1
        )

        if existing:
            return existing

        return Product.create({
            'name':
                self.official_product_name
                or self.product_name,

            'default_code':
                self.nie_number,

            'type':
                'consu',
        })