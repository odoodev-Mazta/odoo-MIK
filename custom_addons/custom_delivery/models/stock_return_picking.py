from odoo import models


class StockReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'

    def _create_returns(self):
        new_picking_id, pick_type_id = super()._create_returns()
        if new_picking_id:
            new_picking = self.env['stock.picking'].browse(new_picking_id)
            original_picking = self.picking_id
            if original_picking.mou_id and not new_picking.mou_id:
                new_picking.mou_id = original_picking.mou_id.id
        return new_picking_id, pick_type_id