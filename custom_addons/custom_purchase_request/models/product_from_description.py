from collections import OrderedDict

from markupsafe import Markup, escape

from odoo import fields, models
from odoo.exceptions import UserError


class ProductFromDescriptionWizard(models.TransientModel):
    """Ubah description PR/PO yang terlanjur diketik bebas menjadi produk baru.

    Contoh: baris PR berproduk "STIKER YUPO" dengan description
    "STIKER GLYDHERMA 10 GR - YOSOE KAWAI - YUPO" => dibuat produk bernama
    "STIKER GLYDHERMA 10 GR - YOSOE KAWAI - YUPO" (salinan STIKER YUPO), lalu
    product_id baris PR/PO/rincian customer dialihkan ke produk baru itu.
    """
    _name = 'product.from.description.wizard'
    _description = 'Buat Produk dari Description PR/PO'

    state = fields.Selection([('draft', 'Draft'), ('preview', 'Preview'), ('done', 'Selesai')], default='draft')
    skip_received = fields.Boolean(
        string='Lewati PO yang sudah diterima', default=True,
        help='Baris PO yang sudah ada receipt/qty diterima tidak diubah, agar stok dan PO tetap cocok.',
    )
    summary = fields.Html(string='Ringkasan', readonly=True, sanitize=False)

    # ------------------------------------------------------------------
    @staticmethod
    def _clean(text):
        return ' '.join((text or '').split())

    def _same_as_product(self, desc, product):
        return desc in {self._clean(product.display_name), self._clean(product.name)}

    def _po_line_received(self, line):
        return bool(line.qty_received) or bool(line.move_ids.filtered(lambda m: m.state != 'cancel'))

    def _collect(self):
        """Kelompokkan baris yang description-nya berbeda dari nama produknya.

        Kunci = (produk induk, description). Return OrderedDict key -> dict baris.
        """
        groups = OrderedDict()

        def bucket(product, desc):
            return groups.setdefault((product.id, desc), {
                'parent': product, 'desc': desc,
                'pr_lines': self.env['purchase.request.line'],
                'po_lines': self.env['purchase.order.line'],
                'skipped_po': self.env['purchase.order.line'],
                'cust_lines': self.env['purchase.order.customer.line'],
            })

        pr_lines = self.env['purchase.request.line'].search([
            ('line_type', '=', 'product'), ('display_type', '=', False),
            ('product_id', '!=', False), ('description', '!=', False),
        ])
        for line in pr_lines:
            desc = self._clean(line.description)
            if desc and not self._same_as_product(desc, line.product_id):
                bucket(line.product_id, desc)['pr_lines'] |= line

        po_lines = self.env['purchase.order.line'].search([
            ('display_type', '=', False), ('product_id', '!=', False), ('name', '!=', False),
        ])
        for line in po_lines:
            desc = self._clean(line.name)
            if not desc or self._same_as_product(desc, line.product_id):
                continue
            if self.skip_received and self._po_line_received(line):
                bucket(line.product_id, desc)['skipped_po'] |= line
            else:
                bucket(line.product_id, desc)['po_lines'] |= line

        cust_lines = self.env['purchase.order.customer.line'].search([
            ('product_id', '!=', False), ('description', '!=', False),
        ])
        for line in cust_lines:
            desc = self._clean(line.description)
            if not desc or self._same_as_product(desc, line.product_id) or line.allocated_qty:
                continue
            group = bucket(line.product_id, desc)
            blocked = group['skipped_po'].filtered(lambda l: l.order_id == line.order_id)
            if not blocked:
                group['cust_lines'] |= line

        return OrderedDict(
            (key, g) for key, g in groups.items()
            if g['pr_lines'] or g['po_lines'] or g['cust_lines']
        )

    def _find_existing_product(self, desc):
        return self.env['product.product'].with_context(active_test=False).search(
            [('name', '=', desc)], limit=1)

    # ------------------------------------------------------------------
    def _render(self, groups, converted=False):
        rows = Markup('')
        for g in groups.values():
            existing = self._find_existing_product(g['desc'])
            rows += Markup(
                '<tr><td>{parent}</td><td>{desc}</td><td>{status}</td>'
                '<td class="text-end">{pr}</td><td class="text-end">{po}</td>'
                '<td class="text-end">{cust}</td><td class="text-end">{skip}</td></tr>'
            ).format(
                parent=g['parent'].display_name, desc=g['desc'],
                status='Pakai produk yang sudah ada' if existing else ('Dibuat' if converted else 'Akan dibuat'),
                pr=len(g['pr_lines']), po=len(g['po_lines']), cust=len(g['cust_lines']),
                skip=len(g['skipped_po']),
            )
        return Markup(
            '<table class="table table-sm"><thead><tr><th>Produk Induk</th><th>Produk Baru (dari description)</th>'
            '<th>Status</th><th class="text-end">Baris PR</th><th class="text-end">Baris PO</th>'
            '<th class="text-end">Customer PR</th><th class="text-end">PO dilewati</th></tr></thead>'
            '<tbody>{rows}</tbody></table>'
        ).format(rows=rows)

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
            'view_mode': 'form', 'target': 'new',
        }

    def action_preview(self):
        self.ensure_one()
        groups = self._collect()
        if not groups:
            raise UserError('Tidak ada description PR/PO yang berbeda dari nama produknya.')
        self.write({'state': 'preview', 'summary': self._render(groups)})
        return self._reopen()

    def action_convert(self):
        self.ensure_one()
        groups = self._collect()
        for g in groups.values():
            product = self._find_existing_product(g['desc'])
            if not product:
                new_tmpl = g['parent'].product_tmpl_id.copy({
                    'name': g['desc'], 'default_code': False, 'barcode': False,
                })
                product = new_tmpl.product_variant_id
            g['pr_lines'].write({'product_id': product.id})
            g['po_lines'].write({'product_id': product.id})
            g['cust_lines'].write({'product_id': product.id})
        self.write({'state': 'done', 'summary': self._render(groups, converted=True)})
        return self._reopen()
