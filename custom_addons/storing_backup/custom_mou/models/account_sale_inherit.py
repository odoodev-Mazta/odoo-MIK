from odoo import models, fields

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    mou_id = fields.Many2one('draft.maklon', string='No. MOU', domain=[('state', '=', 'mou')])

class AccountMove(models.Model):
    _inherit = 'account.move'

    mou_id = fields.Many2one('draft.maklon', string='No. MOU', domain=[('state', '=', 'mou')])

    def action_post(self):
        res = super(AccountMove, self).action_post()
        for rec in self:
            if rec.mou_id and rec.mou_state:
                container = self.env['mou.container'].search([('mou_id', '=', rec.mou_id.id)], limit=1)

                actual_field_name = f"{rec.mou_state[:4]}_actual_date"

                vals = {
                    'mou_id': rec.mou_id.id,
                    actual_field_name: rec.date,
                }

                if container:
                    container.write(vals)
                else:
                    self.env['mou.container'].create(vals)
        return res

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    mou_id = fields.Many2one('draft.maklon', string='No. MOU', domain=[('state', '=', 'mou')])

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    mou_id = fields.Many2one('draft.maklon', string='No. MOU', domain=[('state', '=', 'mou')])