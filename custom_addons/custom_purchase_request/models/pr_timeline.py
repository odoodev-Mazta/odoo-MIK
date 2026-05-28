from odoo import models, api
from datetime import datetime

class PurchaseRequestTimeline(models.Model):
    _name = 'purchase.request.timeline'
    _description = 'Purchase Request Timeline'

    @api.model
    def get_dashboard_data(self):
        prs = self.env['purchase.request'].search([])
        result = []

        for pr in prs:
            # PO
            po = self.env['purchase.order'].search([
                ('origin', '=', pr.name)
            ], limit=1)

            # UD
            ud = self.env['usulan.usulan.dana'].search([
                ('description', 'like', f'Generate dari PR {pr.name}')
            ], limit=1)

            # BD
            bd = None
            if 'bank.disbursement' in self.env.registry:
                bd = self.env['bank.disbursement'].search([
                    ('purchase_request_id', '=', pr.id)
                ], limit=1)

            # Approval date: ambil dari write_date saat state berubah ke pr/ud
            approval_done = pr.state in ('pr', 'ud')

            stages = [
                {
                    'code': 'pr',
                    'label': 'PR',
                    'status': 'done',
                    'date': pr.create_date.strftime('%d-%m-%Y') if pr.create_date else '-',
                },
                {
                    'code': 'approval',
                    'label': 'Approval',
                    'status': 'done' if approval_done else 'pending',
                    'date': pr.write_date.strftime('%d-%m-%Y') if approval_done and pr.write_date else '-',
                },
                {
                    'code': 'vendor',
                    'label': 'Vendor',
                    'status': 'done' if pr.vendor_id else 'pending',
                    'date': '-',
                },
                {
                    'code': 'po',
                    'label': 'PO',
                    'status': 'done' if po else 'pending',
                    'date': po.date_order.strftime('%d-%m-%Y') if po and po.date_order else '-',
                },
                {
                    'code': 'ud',
                    'label': 'UD',
                    'status': 'done' if ud else 'pending',
                    'date': ud.create_date.strftime('%d-%m-%Y') if ud and ud.create_date else '-',
                },
                {
                    'code': 'bd',
                    'label': 'BD',
                    'status': 'done' if bd else 'pending',
                    'date': bd.create_date.strftime('%d-%m-%Y') if bd and bd.create_date else '-',
                },
            ]

            done_count = len([s for s in stages if s['status'] == 'done'])
            progress = int(done_count / len(stages) * 100)
            completed = done_count == len(stages)

            result.append({
                'id': pr.id,
                'pr_no': pr.name,
                'department': pr.department_id.name if pr.department_id else '-',
                'department_id': pr.department_id.id if pr.department_id else False,
                'vendor': pr.vendor_id.name if pr.vendor_id else '-',
                'product_summary': pr.product_summary or '-',
                'total_qty': pr.total_qty,
                'total_amount': pr.total_amount,
                'currency_symbol': pr.currency_id.symbol if pr.currency_id else 'Rp',
                'deadline': pr.estimated_date.strftime('%d-%m-%Y') if pr.estimated_date else '-',
                'is_urgent': pr.is_urgent,
                'status': 'Complete' if completed else 'On Progress',
                'progress': progress,
                'stages': stages,
                'pr_date': pr.create_date.strftime('%d-%m-%Y') if pr.create_date else '-',
                'po_name': po.name if po else '-',
                'ud_name': ud.name if ud else '-',
                'bd_name': bd.name if bd and bd.name else '-',
            })

        return result

    @api.model
    def get_departments(self):
        departments = self.env['hr.department'].search([])
        return [{'id': d.id, 'name': d.name} for d in departments]