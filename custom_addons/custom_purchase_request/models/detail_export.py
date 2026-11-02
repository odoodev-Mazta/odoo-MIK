import base64
import datetime
import io

import pytz
import xlsxwriter

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class DetailExportFile(models.TransientModel):
    _name = 'detail.export.file'
    _description = 'File Export Detail'

    file_name = fields.Char(required=True)
    file_data = fields.Binary(attachment=False)


class DetailExportWizard(models.TransientModel):
    _name = 'detail.export.wizard'
    _description = 'Pilihan Export Detail'

    res_model = fields.Selection([
        ('sale.order', 'Sales Order'),
        ('purchase.order', 'PQ/PO'),
        ('purchase.request', 'Purchase Request'),
    ], required=True)
    export_mode = fields.Selection([
        ('all', 'Semua'),
        ('date', 'Rentang Tanggal'),
    ], string='Export', required=True, default='all')
    date_from = fields.Date(string='Dari Tanggal')
    date_to = fields.Date(string='Sampai Tanggal')
    date_label = fields.Char(compute='_compute_date_label')

    @api.depends('res_model')
    def _compute_date_label(self):
        for wizard in self:
            if not wizard.res_model:
                wizard.date_label = ''
                continue
            Model = self.env[wizard.res_model]
            wizard.date_label = Model._fields[Model._detail_export_date_field].string

    def _get_export_domain(self):
        self.ensure_one()
        if self.export_mode == 'all':
            return []
        if not self.date_from or not self.date_to:
            raise UserError(_('Isi Dari Tanggal dan Sampai Tanggal.'))
        if self.date_from > self.date_to:
            raise UserError(_('Dari Tanggal tidak boleh setelah Sampai Tanggal.'))
        Model = self.env[self.res_model]
        date_field = Model._detail_export_date_field
        start, end = self.date_from, self.date_to
        if Model._fields[date_field].type == 'datetime':
            # tanggal di popup = tanggal lokal user, di database disimpan UTC
            tz = self.env.tz
            start = tz.localize(datetime.datetime.combine(start, datetime.time.min))
            end = tz.localize(datetime.datetime.combine(end, datetime.time.max))
            start = start.astimezone(pytz.utc).replace(tzinfo=None)
            end = end.astimezone(pytz.utc).replace(tzinfo=None)
        return [(date_field, '>=', start), (date_field, '<=', end)]

    def action_export(self):
        self.ensure_one()
        records = self.env[self.res_model].search(self._get_export_domain(), order='id desc')
        if not records:
            raise UserError(_('Tidak ada data untuk di-export.'))
        return records._action_download_detail()


class DetailExportMixin(models.AbstractModel):
    _name = 'detail.export.mixin'
    _description = 'Export Header dan Detail ke Excel'

    # {path field: judul kolom}
    _detail_export_columns = {}
    # field tanggal untuk filter rentang di popup export
    _detail_export_date_field = 'date_order'

    def _get_detail_export_columns(self):
        """Hanya kolom yang field-nya ada, karena sebagian berasal dari modul lain."""
        return {
            path: label
            for path, label in self._detail_export_columns.items()
            if path.split('/')[0] in self._fields
        }

    def _get_detail_export_content(self):
        columns = self._get_detail_export_columns()
        rows = self.export_data(list(columns))['datas']

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Data')
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})
        for col, label in enumerate(columns.values()):
            sheet.write(0, col, label, header_format)
            sheet.set_column(col, col, max(len(label) + 2, 14))
        datetime_format = workbook.add_format({'num_format': 'yyyy-mm-dd hh:mm'})
        date_format = workbook.add_format({'num_format': 'yyyy-mm-dd'})
        for row_index, row in enumerate(rows, start=1):
            for col, value in enumerate(row):
                if isinstance(value, datetime.datetime):
                    local_value = fields.Datetime.context_timestamp(self, value).replace(tzinfo=None)
                    sheet.write_datetime(row_index, col, local_value, datetime_format)
                elif isinstance(value, datetime.date):
                    sheet.write_datetime(row_index, col, value, date_format)
                elif value is None or value is False:
                    sheet.write_blank(row_index, col, None)
                else:
                    sheet.write(row_index, col, value)
        sheet.freeze_panes(1, 0)
        sheet.autofilter(0, 0, max(len(rows), 1), len(columns) - 1)
        workbook.close()
        return output.getvalue()

    def action_export_detail(self):
        """Tombol di list: buka popup pilihan export, centang di list tidak dipakai."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Export Detail'),
            'res_model': 'detail.export.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_res_model': self._name},
        }

    def _action_download_detail(self):
        file_name = '%s_detail_%s.xlsx' % (
            self._name.replace('.', '_'),
            fields.Date.context_today(self).strftime('%Y%m%d'),
        )
        export_file = self.env['detail.export.file'].create({
            'file_name': file_name,
            'file_data': base64.b64encode(self._get_detail_export_content()),
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/detail.export.file/{export_file.id}/file_data/{file_name}?download=true',
            'target': 'self',
        }


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'detail.export.mixin']

    _detail_export_columns = {
        'name': 'No. SO',
        'state': 'Status',
        'partner_id': 'Customer',
        'date_order': 'Tgl Order',
        'mou_id': 'No. MOU',
        'timeline_stage': 'Tahapan',
        'is_repeat_order': 'Repeat Order',
        'marketing_sequence': 'No. PO Produksi',
        'amount_total': 'Total',
        'order_line/product_id': 'Produk',
        'order_line/name': 'Deskripsi',
        'order_line/product_uom_qty': 'Qty',
        'order_line/product_uom_id': 'Satuan',
        'order_line/price_unit': 'Harga Satuan',
        'order_line/discount': 'Diskon (%)',
        'order_line/tax_ids': 'Pajak',
        'order_line/price_subtotal': 'Subtotal',
        'order_line/qty_delivered': 'Qty Terkirim',
        'order_line/qty_invoiced': 'Qty Ditagih',
    }

    def get_import_templates(self):
        return [{
            'label': _('Template Import SO'),
            'template': '/custom_purchase_request/static/xls/template_import_so.xlsx',
        }]


class PurchaseOrder(models.Model):
    _name = 'purchase.order'
    _inherit = ['purchase.order', 'detail.export.mixin']

    _detail_export_columns = {
        'name': 'No. PQ/PO',
        'state': 'Status',
        'partner_id': 'Vendor',
        'partner_ref': 'Ref. Vendor',
        'date_order': 'Tgl Order',
        'purchase_request_id': 'No. PR',
        'customer_id': 'Customer',
        'mou_id': 'No. MOU',
        'sale_order_id': 'No. SO',
        'origin': 'Sumber',
        'currency_id': 'Mata Uang',
        'amount_total': 'Total',
        'order_line/product_id': 'Produk',
        'order_line/name': 'Deskripsi',
        'order_line/product_qty': 'Qty',
        'order_line/product_uom_id': 'Satuan',
        'order_line/price_unit': 'Harga Satuan',
        'order_line/discount': 'Diskon (%)',
        'order_line/tax_ids': 'Pajak',
        'order_line/date_planned': 'Tgl Estimasi Tiba',
        'order_line/price_subtotal': 'Subtotal',
        'order_line/qty_received': 'Qty Diterima',
        'order_line/qty_invoiced': 'Qty Ditagih',
        'setup_line_ids/setup_item_id': 'Item Setup',
        'setup_line_ids/description': 'Deskripsi Item Setup',
        'setup_line_ids/item_qty': 'Qty Item Setup',
    }

    def get_import_templates(self):
        return [{
            'label': _('Template Import PQ/PO'),
            'template': '/custom_purchase_request/static/xls/template_import_pq_po.xlsx',
        }]


class PurchaseRequest(models.Model):
    _name = 'purchase.request'
    _inherit = ['purchase.request', 'detail.export.mixin']

    _detail_export_date_field = 'date_usulan'

    _detail_export_columns = {
        'name': 'No. PR',
        'state': 'Status',
        'date_usulan': 'Tgl Usulan',
        'department_id': 'Departemen',
        'pic_dept': 'PIC Departemen',
        'whatsapp_no': 'No WhatsApp',
        'estimated_date': 'Estimasi Tiba',
        'deliver_to': 'Dikirim Ke',
        'is_urgent': 'Urgent',
        'customer_id': 'Customer',
        'mou_id': 'No. MOU',
        'sale_order_id': 'No. SO',
        'usulan_dana_id': 'No. Usulan Dana',
        'recommended_vendor_1': 'Vendor 1',
        'recommended_vendor_2': 'Vendor 2',
        'currency_id': 'Mata Uang',
        'total_qty': 'Total Qty',
        'total_amount': 'Total Harga',
        'request_line_ids/line_type': 'Jenis Baris',
        'request_line_ids/product_id': 'Produk',
        'request_line_ids/setup_item_id': 'Item Setup',
        'request_line_ids/description': 'Deskripsi',
        'request_line_ids/product_qty': 'Qty',
        'request_line_ids/item_qty': 'Qty Item Setup',
        'request_line_ids/product_uom': 'Satuan',
        'request_line_ids/price_unit': 'Harga Satuan',
        'request_line_ids/tax_ids': 'Pajak',
        'request_line_ids/date_planned': 'Tgl Rencana',
        'request_line_ids/price_subtotal': 'Subtotal',
        'is_bulk_purchase': 'Pembelian Bulk',
        'bulk_line_ids/mou_id': 'Bulk: No. MOU',
        'bulk_line_ids/product_id': 'Bulk: Produk',
        'bulk_line_ids/qty': 'Bulk: Qty',
        'bulk_line_ids/price_unit': 'Bulk: Harga Satuan',
        'bulk_line_ids/price_subtotal': 'Bulk: Subtotal',
        'bulk_line_ids/note': 'Bulk: Catatan',
    }

    def get_import_templates(self):
        return [{
            'label': _('Template Import PR'),
            'template': '/custom_purchase_request/static/xls/template_import_pr.xlsx',
        }]
