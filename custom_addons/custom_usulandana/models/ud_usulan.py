from odoo import models, fields, api, exceptions


class UsulanUsulanDana(models.Model):
    _name = 'usulan.usulan.dana'
    _description = 'Usulan Dana'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_created desc'

    name = fields.Char(string='No Usulan', readonly=True, default='New')
    department_id = fields.Many2one('hr.department', string='Departemen', default=lambda self: self.env.user.employee_id.department_id.id, required=True)
    pic_id = fields.Many2one('hr.employee', string='PIC (Karyawan)')
    pic_phone = fields.Char(string='No WA PIC')
    pic_bank_account = fields.Char(string='Data Rekening PIC')

    vendor_id = fields.Many2one('res.partner', string='Vendor', domain="[('supplier_rank', '>', 0)]")
    # Alamat & WA otomatis ditarik dari master data res.partner, tapi masih bisa diedit manual (readonly=False)
    vendor_address = fields.Char(string='Alamat Vendor', related='vendor_id.street', readonly=False)
    vendor_phone = fields.Char(string='No WA Vendor', related='vendor_id.phone', readonly=False)

    payment_method = fields.Selection([
        ('cash', 'Kas Kecil / Tunai'),
        ('transfer', 'Transfer Bank'),
        ('va', 'Virtual Account (VA)'),
        ('ewallet', 'OVO / GoPay / Dana'),
        ('giro', 'Cek / Giro')
    ], string='Metode Payment', default='transfer')
    vendor_bank_account = fields.Char(string='No Rekening Vendor')

    date_created = fields.Datetime(string='Tgl Dibuat', default=fields.Datetime.now, readonly=True)
    description = fields.Text(string='Keterangan')
    date_submitted = fields.Datetime(string='Tgl Diajukan', readonly=True)

    # One2many ke model Lines
    line_ids = fields.One2many('usulan.usulan.dana.line', 'usulan_id', string='Detail Item')

    amount_invoice_raw = fields.Monetary(string='Nilai Invoice', compute='_compute_amount_total', store=True)
    amount_discount = fields.Monetary(string='Diskon', compute='_compute_amount_total', store=True)

    # Grand Total (Header)
    amount_dpp = fields.Monetary(string='DPP', compute='_compute_amount_total', store=True)
    amount_ppn = fields.Monetary(string='PPN(11%)', compute='_compute_amount_total', store=True)
    amount_total = fields.Monetary(string='Total Nilai Usulan', compute='_compute_amount_total', store=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    is_ppn = fields.Boolean(string='PPN 11%', default=False, tracking=True)
    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Lampiran Invoice/Dokumen',
        help="Unggah semua dokumen pendukung di sini"
    )

    # Field Termin Pembayaran (Pindah ke Notebook)
    # payment_term_id = fields.Many2one('account.payment.term', string='Termin Pembayaran')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting_head', 'Waiting Head Dept'),
        ('waiting_coo', 'Waiting COO'),
        ('waiting_ceo', 'Waiting CEO'),
        ('waiting_finance', 'Waiting Finance'),
        ('approve', 'Approved'),
        ('rilis', 'Rilis'),
        ('reject', 'Rejected'),
        ('cancel', 'Cancelled')
    ], string='Status', default='draft', tracking=True)

    # Computed Fields untuk List View
    jenis = fields.Selection([
        ('draft', 'Draft'),
        ('usulan_dana', 'Usulan Dana')
    ], string='Jenis', compute='_compute_list_status', store=True)

    status_approval = fields.Selection([
        ('waiting', 'Menunggu'),
        ('approved', 'Approved'),
        ('rejected', 'Ditolak')
    ], string='Status Approval', compute='_compute_list_status', store=True)

    status_plan_payment = fields.Selection([
        ('waiting', 'Waiting Plan'),
        ('planned', 'Planned')
    ], string='Status Plan Payment', default='waiting')

    status_payment = fields.Selection([
        ('unpaid', 'Belum Rilis'),
        ('paid', 'Sudah Rilis')
    ], string='Status Payment', compute='_compute_list_status', store=True)

    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        domain=[('state', 'in', ['purchase', 'done'])],
        help="Pilih PO untuk mengisi usulan secara otomatis"
    )

    req_head = fields.Boolean(string='Req Head', copy=False)
    req_coo = fields.Boolean(string='Req COO', copy=False)
    req_ceo = fields.Boolean(string='Req CEO', copy=False)
    is_my_approval = fields.Boolean(
        string='Butuh Approval Saya',
        compute='_compute_is_my_approval',
        search='_search_is_my_approval'  # [BARU] Tambahkan ini agar bisa difilter di XML
    )

    @api.onchange('purchase_order_id')
    def _onchange_purchase_order_id(self):
        if not self.purchase_order_id:
            return

        self.vendor_id = self.purchase_order_id.partner_id.id
        self.currency_id = self.purchase_order_id.currency_id.id
        self.description = f"Tagihan atas PO: {self.purchase_order_id.name}"

        new_lines = []
        for line in self.purchase_order_id.order_line:
            line_values = {
                'item_name': line.name,
                'quantity': line.product_qty,
                'price_unit': line.price_unit,
                'tax_ids': [(6, 0, line.tax_ids.ids)],
                # Jika kamu punya field UoM atau Account, masukkan juga di sini
                # 'uom_id': line.product_uom.id,
            }
            new_lines.append((0, 0, line_values))

        self.line_ids = [(5, 0, 0)] + new_lines

    @api.onchange('is_ppn')
    def _onchange_is_ppn(self):
        """ Menyuntikkan atau mencabut PPN 11% di semua baris item saat toggle diklik """
        tax_11 = self.env['account.tax'].search([
            ('type_tax_use', '=', 'purchase'),
            ('name', 'ilike', '11%'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)

        if self.is_ppn and not tax_11:
            from odoo import exceptions
            raise exceptions.UserError(
                "Pajak PPN 11% tidak ditemukan di sistem! "
                "Pastikan di master data Accounting (Taxes) ada pajak Pembelian bernama '11%' untuk perusahaan ini."
            )

        for line in self.line_ids:
            if self.is_ppn and tax_11:
                line.tax_ids = tax_11
            else:
                line.tax_ids = False

    def _compute_is_my_approval(self):
        for record in self:
            user = self.env.user
            is_head = user.has_group('custom_usulandana.group_head_dept')
            is_coo = user.has_group('custom_usulandana.group_coo')
            is_ceo = user.has_group('custom_usulandana.group_ceo')
            is_finance = user.has_group('custom_usulandana.group_finance')

            record.is_my_approval = False
            if record.state == 'waiting_head' and is_head:
                record.is_my_approval = True
            elif record.state == 'waiting_coo' and is_coo:
                record.is_my_approval = True
            elif record.state == 'waiting_ceo' and is_ceo:
                record.is_my_approval = True
            elif record.state == 'waiting_finance' and is_finance:
                record.is_my_approval = True

    def _search_is_my_approval(self, operator, value):
        """ Fungsi ini dipanggil Odoo saat user mengklik filter 'Menunggu Persetujuan Saya' """
        user = self.env.user
        is_finance = user.has_group('custom_usulandana.group_finance')

        if operator == '=' and value is True:
            # Jika user adalah Finance, tampilkan SEMUA yang bukan draft/cancel
            if is_finance:
                return [('state', 'not in', ['draft', 'cancel', 'reject'])]

            # Jika bukan finance, filter sesuai jabatan masing-masing
            valid_states = []
            if user.has_group('custom_usulandana.group_head_dept'):
                valid_states.append('waiting_head')
            if user.has_group('custom_usulandana.group_coo'):
                valid_states.append('waiting_coo')
            if user.has_group('custom_usulandana.group_ceo'):
                valid_states.append('waiting_ceo')

            return [('state', 'in', valid_states)]

        return []

    @api.depends('line_ids.price_subtotal', 'line_ids.ppn_amount', 'line_ids.grand_total', 'line_ids.price_raw',
                 'line_ids.discount_amount')
    def _compute_amount_total(self):
        for record in self:
            record.amount_invoice_raw = sum(record.line_ids.mapped('price_raw'))
            record.amount_discount = sum(record.line_ids.mapped('discount_amount'))

            record.amount_dpp = sum(record.line_ids.mapped('price_subtotal'))
            record.amount_ppn = sum(record.line_ids.mapped('ppn_amount'))
            record.amount_total = sum(record.line_ids.mapped('grand_total'))

    @api.depends('state')
    def _compute_list_status(self):
        for record in self:
            record.jenis = 'draft' if record.state == 'draft' else 'usulan_dana'

            if record.state == 'to_approve':
                record.status_approval = 'waiting'
            elif record.state in ('approve', 'rilis'):
                record.status_approval = 'approved'
            elif record.state == 'reject':
                record.status_approval = 'rejected'
            else:
                record.status_approval = False

            record.status_payment = 'paid' if record.state == 'rilis' else 'unpaid'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('usulan.usulan.dana') or 'New'
        return super().create(vals_list)

    def action_submit(self):
        """ Saat diajukan, Odoo mencari tahu harus lari ke mana dokumen ini """
        for record in self:
            total = record.amount_total

            domain = [('min_amount', '<=', total)]
            rules = self.env['usulan.approval.setup'].search(domain)

            # Filter manual untuk max_amount (karena 0 artinya unlimited)
            valid_rule = False
            for rule in rules:
                if rule.max_amount == 0 or rule.max_amount >= total:
                    valid_rule = rule
                    break

            if not valid_rule:
                raise exceptions.UserError(
                    f"Sistem tidak menemukan Setup Approval untuk nominal {total}. Hubungi Admin!")

            record.req_head = valid_rule.need_head_dept
            record.req_coo = valid_rule.need_coo
            record.req_ceo = valid_rule.need_ceo

            if record.req_head:
                record.state = 'waiting_head'
            elif record.req_coo:
                record.state = 'waiting_coo'
            elif record.req_ceo:
                record.state = 'waiting_ceo'
            else:
                record.state = 'waiting_finance'

    def action_approve_head(self):
        for record in self:
            if record.req_coo:
                record.state = 'waiting_coo'
            elif record.req_ceo:
                record.state = 'waiting_ceo'
            else:
                record.state = 'waiting_finance'

    def action_approve_coo(self):
        for record in self:
            if record.req_ceo:
                record.state = 'waiting_ceo'
            else:
                record.state = 'waiting_finance'

    def action_approve_ceo(self):
        for record in self:
            record.state = 'waiting_finance'

    def action_approve_finance(self):
        """ Ini adalah action_approve yang lama (Final) """
        for record in self:
            record.state = 'approve'

            plan = self.env['usulan.plan.payment'].create({
                'name': f"PP/{record.name}",
                'usulan_dana_id': record.id,
                'department_id': record.department_id.id,
                'description': record.description,
                'state': 'menggantung',
            })

            all_schedules = record.line_ids.mapped('payment_schedule_ids')
            if all_schedules:
                all_schedules.write({'plan_payment_id': plan.id})

    def action_reject(self):
        for record in self:
            record.state = 'reject'

    def action_rilis(self):
        for record in self:
            record.state = 'rilis'

    def action_cancel(self):
        for record in self:
            plans = self.env['usulan.plan.payment'].search([('usulan_dana_id', '=', record.id)])

            schedules = record.line_ids.mapped('payment_schedule_ids')
            vendor_bills = schedules.mapped('vendor_bill_id')

            posted_bills = vendor_bills.filtered(lambda b: b.state == 'posted')
            if posted_bills:
                raise exceptions.UserError(
                    "GAGAL DIBATALKAN!\n"
                    "Usulan Dana ini sudah memiliki Tagihan (Vendor Bill) yang di-posting oleh Finance. "
                    "Silakan minta tim Finance untuk membatalkan (Reset to Draft -> Cancel) tagihan tersebut terlebih dahulu."
                )

            draft_bills = vendor_bills.filtered(lambda b: b.state == 'draft')
            if draft_bills:
                draft_bills.button_cancel()

            if plans:
                plans.write({'state': 'cancel'})
            record.state = 'cancel'

class UsulanUsulanDanaLine(models.Model):
    _name = 'usulan.usulan.dana.line'
    _description = 'Line Usulan Dana'

    usulan_id = fields.Many2one('usulan.usulan.dana', string='Parent')
    item_name = fields.Char(string='Nama Item', required=True)
    setup_item_id = fields.Many2one(
        'usulan.dana.setup',
        string='Nama Item',
        required=True,
        domain="[('state', '=', 'done')]"
    )
    account_id = fields.Many2one(
        'account.account',
        related='setup_item_id.account_id',
        string='COA',
        store=True,
        readonly=True
    )
    quantity = fields.Float(string='Qty', default=1.0)

    # Currency per Line
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    today_rate = fields.Float(string="Today's Currency", help="Exchange rate hari ini")

    price_unit = fields.Monetary(string='Price', currency_field='currency_id')
    discount = fields.Float(string='Discount (%)')
    price_subtotal = fields.Monetary(string='Total', compute='_compute_subtotal', store=True,
                                     currency_field='currency_id')
    ppn_amount = fields.Monetary(string='Nilai PPN', compute='_compute_subtotal', store=True,
                                 currency_field='currency_id')

    grand_total = fields.Monetary(string='Grand Total', compute='_compute_subtotal', store=True,
                                  currency_field='currency_id')
    grand_total_currency = fields.Float(string='GT Currency', compute='_compute_subtotal', store=True)

    # termin bayar
    payment_schedule_ids = fields.One2many('usulan.payment.schedule', 'line_id', string='Jadwal Pembayaran')
    payment_summary = fields.Char(string='Info Termin', compute='_compute_payment_summary', store=True)

    tax_ids = fields.Many2many(
        'account.tax',
        string='Pajak',
        domain="[('type_tax_use', '=', 'purchase')]",
        compute='_compute_tax_ids',
        store=True,
        readonly=False
    )
    price_raw = fields.Monetary(string='Nilai Kotor', compute='_compute_subtotal', store=True,
                                currency_field='currency_id')
    discount_amount = fields.Monetary(string='Nominal Diskon', compute='_compute_subtotal', store=True,
                                      currency_field='currency_id')

    @api.depends('payment_schedule_ids', 'payment_schedule_ids.date_payment')
    def _compute_payment_summary(self):
        for line in self:
            # PENTING: Gunakan .sudo() jika ada kendala akses, dan pastikan memfilter line_id yang tepat
            schedules = line.payment_schedule_ids
            count = len(schedules)
            if count == 0:
                line.payment_summary = "Belum Diset"
            elif count == 1:
                # Ambil tanggal pertama
                date_val = schedules[0].date_payment
                line.payment_summary = f"Jatuh Tempo ({date_val.strftime('%d-%m-%Y')})" if date_val else "Jatuh Tempo"
            else:
                line.payment_summary = f"{count}x Termin"

    @api.depends('usulan_id.is_ppn')
    def _compute_tax_ids(self):
        tax_11 = self.env['account.tax'].search([
            ('type_tax_use', '=', 'purchase'),
            ('name', 'ilike', '11%'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)

        for line in self:
            if line.usulan_id.is_ppn:
                if tax_11:
                    line.tax_ids = [(6, 0, tax_11.ids)]
                else:
                    from odoo import exceptions
                    raise exceptions.UserError(
                        "Pajak dengan nama mengandung '11%' untuk Pembelian tidak ditemukan di master data Accounting!")
            else:
                line.tax_ids = [(5, 0, 0)]

    @api.depends('quantity', 'price_unit', 'discount', 'today_rate', 'usulan_id.is_ppn')
    def _compute_subtotal(self):
        for line in self:
            # 1. Hitung Total (DPP) -> Price * Qty - Discount
            total_awal = line.quantity * line.price_unit
            diskon_nominal = total_awal * (line.discount / 100.0)

            line.price_raw = total_awal
            line.discount_amount = diskon_nominal

            dpp = total_awal - diskon_nominal
            line.price_subtotal = dpp

            # 2. Hitung PPN jika tombol on/off dinyalakan
            ppn = dpp * 0.11 if line.usulan_id.is_ppn else 0.0
            line.ppn_amount = ppn

            # 3. Hitung Grand Total -> DPP + PPN
            gt = dpp + ppn
            line.grand_total = gt

            # 4. Hitung Grand Total Currency -> Grand Total * Rate
            line.grand_total_currency = gt * line.today_rate

    def action_open_payment_wizard(self):
        self.ensure_one()

        # [PERBAIKAN] Gunakan self._origin.id untuk mengecek apakah ID sudah permanen
        if not self._origin.id:
            from odoo import exceptions  # Pastikan exceptions sudah di-import di atas jika belum
            raise exceptions.UserError(
                "Silakan klik ikon awan/tombol 'Save' untuk menyimpan dokumen terlebih dahulu sebelum mengatur termin.")

        existing_lines = []
        for schedule in self.payment_schedule_ids:
            existing_lines.append((0, 0, {
                'date_payment': schedule.date_payment,
                'amount_percentage': schedule.amount_percentage,
                'amount': schedule.amount
            }))

        return {
            'name': 'Atur Termin Pembayaran',
            'type': 'ir.actions.act_window',
            'res_model': 'usulan.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                # [PERBAIKAN] Pastikan ID yang dikirim ke Wizard adalah ID asli (bukan virtual)
                'default_line_id': self._origin.id,
                'default_total_amount': self.grand_total,
                'default_wizard_line_ids': existing_lines,
            }
        }