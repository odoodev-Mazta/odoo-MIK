from odoo import http
from odoo.http import request

class MaztaOrderPortal(http.Controller):

    @http.route(['/my/mazta/orders/<int:order_id>'], type='http', auth="user", website=True)
    def portal_mazta_order_page(self, order_id, **kw):
        order_obj = request.env['mazta.order'].browse(order_id)
        if not order_obj.exists():
            return request.not_found()
        
        # Ubah key dictionary-nya menjadi 'doc'
        return request.render('sale_custom.mazta_portal_template', {'doc': order_obj})