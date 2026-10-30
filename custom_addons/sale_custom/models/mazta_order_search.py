# -*- coding: utf-8 -*-
from datetime import datetime, time
from odoo import models, fields
from odoo.exceptions import UserError

class MaztaOrderSearchWizard(models.TransientModel):
    _name = 'mazta.order.search.wizard'
    _description = 'Wizard Pencarian Lanjutan Mazta Orders'

    name = fields.Char(string='Order Number')
    date_order = fields.Date(string='Order Date')
    partner_id = fields.Many2one('res.partner', string='Customer')
    user_id = fields.Many2one('res.users', string='Salesperson')
    state = fields.Selection([
        ('draft', 'Quotation'),
        ('sale', 'Sales Order'),
        ('done', 'Locked / Done'),
        ('cancel', 'Cancelled')
    ], string='Status')
    min_amount = fields.Float(string='Minimum Total')
    max_amount = fields.Float(string='Maksimum Total')

    def action_search_mazta_orders(self):
        self.ensure_one()
        domain = []
        
        if self.name:
            domain.append(('name', 'ilike', self.name))
        
        if self.date_order:
            start_datetime = datetime.combine(self.date_order, time.min)
            end_datetime = datetime.combine(self.date_order, time.max)
            domain.append(('date_order', '>=', start_datetime))
            domain.append(('date_order', '<=', end_datetime))
            
        if self.partner_id:
            domain.append(('partner_id', '=', self.partner_id.id))
        if self.user_id:
            domain.append(('user_id', '=', self.user_id.id))
        if self.state:
            domain.append(('state', '=', self.state))
        if self.min_amount:
            domain.append(('amount_total', '>=', self.min_amount))
        if self.max_amount:
            domain.append(('amount_total', '<=', self.max_amount))

        orders = self.env['mazta.order'].search(domain)
        
        if not orders:
            raise UserError("Result: Tidak ada data Mazta Order yang ditemukan.")

        result_text = f"Result (Ditemukan {len(orders)} Data):\n\n"
        for order in orders:
            result_text += f"- {order.name} | {order.date_order} | {order.partner_id.name or '-'} | Rp {order.amount_total:,.2f} | {order.state}\n"

        raise UserError(result_text)