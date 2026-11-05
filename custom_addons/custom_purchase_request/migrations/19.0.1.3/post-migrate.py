from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Baris Customer PR hasil Merge yang belum punya No. PR: isi dari kolom Origin PO-nya."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    orders = env['purchase.order'].search([('customer_line_ids.request_id', '=', False), ('origin', '!=', False)])
    orders._sync_header_from_customer_lines()
