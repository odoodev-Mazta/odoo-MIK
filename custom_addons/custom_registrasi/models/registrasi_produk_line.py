import re

from markupsafe import Markup

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
        copy=False,
    )
    product_name_revision_count = fields.Integer(
        string='Product Name Revision Count',
        default=0,
        copy=False,
    )
    confirmation_counter = fields.Integer(
        string='BPOM Confirmation Counter',
        default=0,
        copy=False,
    )

    nie_number = fields.Char(
        string='NIE Number',
        copy=False,
    )
    nie_issued_date = fields.Date(
        string='NIE Issued Date',
        copy=False,
    )
    nie_expired_date = fields.Date(
        string='NIE Expired Date',
        copy=False,
    )
    product_template_id = fields.Many2one(
        comodel_name='product.template',
        string='Product',
        copy=False,
    )
    nie_product_id = fields.Many2one(
        comodel_name='product.template',
        string='Data Produk NIE',
        copy=False,
        readonly=True,
        help='Data Produk yang dibuat saat NIE Issued.',
    )

    # Perubahan field ini dicatat di chatter Registrasi Produk (induknya), karena baris
    # produk tidak punya chatter sendiri.
    _TRACKED_FIELDS = (
        'official_product_name',
        'product_name_revision_count',
        'confirmation_counter',
        'nie_number',
        'nie_issued_date',
        'nie_expired_date',
        'product_template_id',
        'nie_product_id',
    )

    def write(self, vals):
        tracked = [name for name in self._TRACKED_FIELDS if name in vals]
        old_values = {line.id: {name: line[name] for name in tracked} for line in self} if tracked else {}
        result = super().write(vals)
        for line in self.filtered('produk_id'):
            changes = []
            for name in tracked:
                before, after = old_values[line.id][name], line[name]
                if before != after:
                    changes.append((line._fields[name].string, line._format_tracked_value(before),
                                    line._format_tracked_value(after)))
            if changes:
                items = Markup('').join(
                    Markup('<li>%s: %s &rarr; %s</li>') % change for change in changes
                )
                line.produk_id.message_post(
                    body=Markup('<b>%s</b><ul>%s</ul>') % (line.official_product_name or line.display_name, items),
                    subtype_xmlid='mail.mt_note',
                )
        return result

    def _nie_product_name(self):
        """Brand Official Product Name Primary Packaging Netto (tanpa tanda strip)."""
        self.ensure_one()
        packaging = dict(self._fields['primary_packaging'].selection).get(self.primary_packaging)
        parts = [self.produk_id.brand_name, self.official_product_name, packaging, '%s g/ml' % self.netto]
        return ' '.join(' '.join(str(part).split()) for part in parts if part)

    def _create_nie_product(self):
        """Buat Data Produk untuk baris ini. Bila produk bernama persis sama sudah ada, dipakai (tidak dobel)."""
        self.ensure_one()
        if self.nie_product_id:
            return self.nie_product_id
        name = self._nie_product_name()
        Product = self.env['product.template'].sudo()
        # '=ilike' memakai pola SQL: karakter khusus di nama harus di-escape agar cocok persis.
        escaped = re.sub(r'([\\%_])', r'\\\1', name)
        product = Product.search([('name', '=ilike', escaped)], limit=1)
        if not product:
            vals = {'name': name, 'type': 'consu', 'sale_ok': True, 'purchase_ok': False,
                    'registrasi_nie_number': self.nie_number}
            if 'is_storable' in Product._fields:
                vals['is_storable'] = True
            product = Product.create(vals)
        elif not product.registrasi_nie_number:
            product.registrasi_nie_number = self.nie_number
        values = {'nie_product_id': product.id}
        if not self.product_template_id:
            values['product_template_id'] = product.id
        self.write(values)
        return product

    def _format_tracked_value(self, value):
        if isinstance(value, models.BaseModel):
            return value.display_name or '-'
        return str(value) if value not in (False, None, '') else '-'

    # def _create_or_link_product_template(self):
    #     self.ensure_one()
    #
    #     Product = self.env['product.template']
    #
    #     existing = Product.search(
    #         [
    #             ('default_code', '=', self.nie_number)
    #         ],
    #         limit=1
    #     )
    #
    #     if existing:
    #         return existing
    #
    #     return Product.create({
    #         'name':
    #             self.official_product_name
    #             or self.product_name,
    #
    #         'default_code':
    #             self.nie_number,
    #
    #         'type':
    #             'consu',
    #     })