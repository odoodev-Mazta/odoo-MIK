from markupsafe import Markup

from odoo import api, fields, models


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
    official_product_id = fields.Many2one(
        comodel_name='product.template',
        string='Official Product Name (RO Drafted)',
        copy=False,
        help='Cari produk yang sudah ada, atau ketik nama baru lalu Create untuk membuat produk baru. '
             'Namanya otomatis disimpan sebagai Official Product Name.',
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

    @api.onchange('official_product_id')
    def _onchange_official_product_id(self):
        for line in self:
            line.official_product_name = line.official_product_id.display_name or False

    def _mirror_official_name(self, vals):
        """Pilihan produk resmi selalu menjadi Official Product Name (teks) yang dipakai di seluruh proses."""
        if 'official_product_id' in vals and 'official_product_name' not in vals:
            product = self.env['product.template'].browse(vals['official_product_id'])
            vals = dict(vals, official_product_name=product.display_name or False)
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([self._mirror_official_name(vals) for vals in vals_list])

    @api.model
    def _link_official_products(self):
        """Tiap Upgrade: nama resmi lama yang persis sama dengan nama produk ditautkan ke produknya."""
        for line in self.search([('official_product_id', '=', False), ('official_product_name', '!=', False)]):
            product = self.env['product.template'].search([('name', '=', line.official_product_name)], limit=1)
            if product:
                line.official_product_id = product

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
    )

    def write(self, vals):
        vals = self._mirror_official_name(vals)
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