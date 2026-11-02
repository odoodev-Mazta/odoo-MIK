from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Delivery Order lama dari SO ber-MOU: isi No MOU dari SO-nya."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    pickings = env['stock.picking'].with_context(active_test=False).search([
        ('mou_id', '=', False),
        ('sale_id.mou_id', '!=', False),
    ])
    for picking in pickings:
        picking.mou_id = picking.sale_id.mou_id
