from odoo import models, fields, api, exceptions


class UsulanUpCountry(models.Model):
    _name = 'usulan.up.country'
    _description = 'Usulan Up Country'
    _inherit = ['mail.activity.mixin', 'mail.thread']
    _order = 'date_created desc'

    name = fields.Char(string="No Usulan", readonly=True, copy=False, default='New')
    date_created = fields.Datetime(string='Tgl Dibuat', default=fields.Datetime.now, readonly=True)
    date_submitted = fields.Datetime(string='Tgl Diajukan', readonly=True)
    department_id = fields.Many2one('hr.department',
                                    string="Departemen",
                                    default=lambda self: self.env.user.employee_id.department_id.id,
                                    readonly=False)
    # tujuan = fields.Char(string='Tujuan', required=True, tracking=True)
    # tipe = fields.Selection([
    #     ('operasional', 'Operasional'),
    #     ('proyek', 'Proyek'),
    #     ('darurat', 'Darurat/Urgent')
    # ], string='Tipe Usulan', required=True)
    employee_id = fields.Many2one('hr.employee', string='Karyawan', readonly=False)
    job_id = fields.Many2one(
        related='employee_id.job_id',
        store=True,
        readonly=True,
        string="Posisi"
    )
    kontak_wa = fields.Char(
        related='employee_id.mobile_phone',
        store=True,
        readonly=True,
        string="Kontak WA"
    )
    email = fields.Char(
        related='employee_id.work_email',
        store=True,
        readonly=True,
        string="Email"
    )
    nama_ktp = fields.Char(string="Nama (Sesuai KTP)", readonly=False)
    nomor_ktp = fields.Char(string="Nomor KTP", readonly=False)

    kota_depart_id = fields.Many2one( 'usulan.master.kota', string="Kota Keberangkatan", readonly=False)
    kota_tujuan_id = fields.Many2one('usulan.master.kota', string="Kota Tujuan", readonly=False)
    tgl_depart = fields.Date(string="Tanggal Keberangkatan", readonly=False)
    tgl_pulang = fields.Date(string="Tanggal Pulang", readonly=False)
    uang_makan = fields.Monetary(string="Uang Makan", readonly=True, currency_id='currency_id')
    uang_lainnya_line_ids = fields.One2many(
        'uang.lainnya.line',
        'up_country_id',
        string="Uang Lainnya"
    )
    uang_lainnya = fields.Monetary(
        string="Total Uang Lainnya",
        compute="_compute_uang_lainnya",
        store=True,
        readonly=True,
        currency_field='currency_id'
    )
    rencana_kerja_line_ids = fields.One2many(
        'rencana.kerja.line',
        'up_country_id',
        string="Rencana Kerja"
    )
    amount = fields.Monetary(string='Nilai Usulan', currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting_head', 'Waiting Head Dept'),
        ('waiting_purchasing', 'Waiting Purchasing'),
        ('approve', 'Approved'),
        ('rilis', 'Rilis'),
        ('reject', 'Rejected'),
        ('cancel', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    req_head = fields.Boolean(copy=False)
    req_purchasing = fields.Boolean(copy=False)

    is_my_approval = fields.Boolean(
        string='Butuh Approval Saya',
        compute='_compute_is_my_approval',
        search='_search_is_my_approval'
    )
    jenis = fields.Selection([
        ('draft', 'Draft'),
        ('usulan_dana', 'UD')
    ], string='Jenis', compute='_compute_kolom_list_view', store=True)
    status_approval = fields.Selection([
        ('waiting', 'Menunggu'),
        ('approved', 'Approved'),
        ('rejected', 'Ditolak')
    ], string='Status Approval', compute='_compute_kolom_list_view', store=True)
    document_type = fields.Selection([
        ('ud', 'Usulan Dana'),
        ('uc', 'Up Country'),
    ],
        default='uc'
    )
    plan_payment_ids = fields.One2many(
        'usulan.plan.payment',
        'usulan_up_country_id'
    )

    status_payment = fields.Selection([
        ('unpaid', 'Belum Rilis'),
        ('paid', 'Rilis')
    ], compute='_compute_status_payment')
    line_uc_ids = fields.One2many('usulan.up.country.line', 'up_country_id', string='Transportasi dan Akomodasi')
    is_advance = fields.Boolean(string="Advance", default=True)
    domestic_intl = fields.Boolean(string="Dalam Negeri")

    def action_open_uang_lainnya_wizard(self):
        self.ensure_one()

        lines = [(0, 0, {
            'keterangan': l.keterangan,
            'amount': l.amount,
        }) for l in self.uang_lainnya_line_ids]

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'uang.lainnya.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_line_ids': lines,
                'active_id': self.id,
            }
        }

    def action_open_rencana_kerja_wizard(self):
        self.ensure_one()

        lines = [(0, 0, {
            'tanggal': l.tanggal,
            'jenis_id': l.jenis_id.id,
            'tipe_visit_id': l.tipe_visit_id.id,
            'tujuan_id': l.tujuan_id.id,
            'deskripsi': l.deskripsi,
        }) for l in self.rencana_kerja_line_ids]

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'rencana.kerja.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_line_ids': lines,
                'active_id': self.id,
            }
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                department = self.env['hr.department'].browse(
                    vals.get('department_id')
                )
                dept_code = department.subkode or 'NON'

                today = fields.Date.today()
                year = today.strftime('%Y')
                month = today.strftime('%m')

                sequence = self.env['ir.sequence'].next_by_code(
                    'usulan.up.country'
                ) or '0001'

                vals['name'] = (
                    f"MIK-{year}/{month}/"
                    f"{dept_code}/UC-"
                    f"{sequence}"
                )

        return super().create(vals_list)

    def action_submit(self):
        for record in self:
            record.req_head = True
            record.req_purchasing = True

            record.state = 'waiting_head'
            record.date_submitted = fields.Datetime.now()

    def action_approve_head(self):
        for record in self:
            record.state = 'waiting_purchasing'

    def action_approve_purchasing(self):
        for record in self:
            record.state = 'approve'

            plan = self.env['usulan.plan.payment'].create({
                'name': f'PP/{record.name}',
                'usulan_up_country_id': record.id,
                'department_id': record.department_id.id,
                'description': f'Up Country {record.name}',
                'state': 'menggantung',
            })

            schedules = self.env['usulan.payment.schedule'].search([
                ('up_country_line_id.up_country_id', '=', record.id)
            ])

            for schedule in schedules:
                schedule.plan_payment_id = plan.id

            if not schedules:
                raise exceptions.UserError("Belum ada termin pembayaran untuk Up Country ini.")

    def action_reject(self):
        for record in self:
            record.state = 'reject'

    def action_rilis(self):
        for record in self:
            record.state = 'rilis'

    def action_cancel(self):
        for record in self:
            record.state = 'cancel'

    def _compute_is_my_approval(self):
        for record in self:
            user = self.env.user

            is_head = user.has_group(
                'custom_usulandana.group_head_dept'
            )

            is_purchasing = user.has_group(
                'custom_usulandana.group_purchasing'
            )

            record.is_my_approval = False
            if record.state == 'waiting_head' and is_head:
                record.is_my_approval = True
            elif record.state == 'waiting_purchasing' and is_purchasing:
                record.is_my_approval = True

    def _search_is_my_approval(self, operator, value):
        user = self.env.user

        if operator == '=' and value is True:
            valid_states = []

            if user.has_group(
                    'custom_usulandana.group_head_dept'
            ):
                valid_states.append('waiting_head')

            if user.has_group(
                    'custom_usulandana.group_purchasing'
            ):
                valid_states.append('waiting_purchasing')
            return [('state', 'in', valid_states)]

        return []

    @api.depends('plan_payment_ids.state')
    def _compute_status_payment(self):
        for rec in self:
            if not rec.plan_payment_ids:
                rec.status_payment = 'unpaid'
                continue

            states = rec.plan_payment_ids.mapped('state')
            if states and all(s == 'rilis' for s in states):
                rec.status_payment = 'paid'
                if rec.state == 'approve':
                    rec.state = 'rilis'
            else:
                rec.status_payment = 'unpaid'

    @api.depends('uang_lainnya_line_ids.amount')
    def _compute_uang_lainnya(self):
        for rec in self:
            rec.uang_lainnya = sum(
                rec.uang_lainnya_line_ids.mapped('amount')
            )

class UsulanUpCountryLine(models.Model):
    _name = 'usulan.up.country.line'
    _description = 'Notebook Line Up Country'

    transportasi = fields.Selection([
        ('pesawat', 'Pesawat'),
        ('bus', 'Bus'),
        ('travel', 'Travel'),
        ('hotel', 'Hotel'),
        ('kapal', 'Kapal'),
    ],string="Transportasi/Akomodasi", readonly=False)
    nama_transportasi = fields.Char(string="Nama Transportasi/Akomodasi", readonly=False)
    dari_kota_id = fields.Many2one('usulan.master.kota', string='Dari')
    ke_kota_id = fields.Many2one('usulan.master.kota', string='Ke')
    tgl_check_depart = fields.Date(string="Tgl Check In/Berangkat", readonly=False)
    notes = fields.Text(string="Catatan", readonly=False)
    up_country_id = fields.Many2one(
        'usulan.up.country',
        string='Parent',
        ondelete='cascade'
    )
    payment_schedule_ids = fields.One2many(
        'usulan.payment.schedule',
        'up_country_line_id',
        string='Jadwal Pembayaran'
    )
    payment_summary = fields.Char(
        string='Info Termin',
        compute='_compute_payment_summary',
        store=True
    )
    waktu_akomodasi = fields.Datetime(string="Set Waktu")
    display_info = fields.Char(
        string="Informasi Waktu",
        compute="_compute_display_info",
        store=True
    )
    tgl_checkout = fields.Date(string="Tanggal Check Out")
    dt_start = fields.Datetime("Waktu Mulai Internal")
    dt_end = fields.Datetime("Waktu Selesai Internal")

    # Field display yang kamu inginkan
    time_info_display = fields.Char(
        string="Ket. Waktu",
        compute="_compute_time_info_display",
        store=True
    )

    @api.onchange('dt_start')
    def _onchange_dt_start(self):
        for rec in self:
            rec.tgl_check_depart = rec.dt_start.date() if rec.dt_start else False

    def write(self, vals):
        if vals.get('dt_start'):
            vals['tgl_check_depart'] = fields.Datetime.to_datetime(
                vals['dt_start']
            ).date()
        return super().write(vals)

    @api.depends('payment_schedule_ids','payment_schedule_ids.date_payment')
    def _compute_payment_summary(self):
        for line in self:
            schedules = line.payment_schedule_ids
            count = len(schedules)

            if count == 0:
                line.payment_summary = "Belum Diset"
            elif count == 1:
                date_val = schedules[0].date_payment

                if date_val:
                    line.payment_summary = (
                        f"Jatuh Tempo "
                        f"({date_val.strftime('%d-%m-%Y')})"
                    )
                else:
                    line.payment_summary = "Jatuh Tempo"
            else:
                line.payment_summary = f"{count}x Termin"

    @api.onchange('transportasi')
    def _onchange_transportasi(self):
        for line in self:

            if not line.up_country_id:
                continue

            if line.transportasi == 'hotel':
                line.dari_kota_id = False
                line.ke_kota_id = False
                continue

            if line.transportasi:
                line.dari_kota_id = line.up_country_id.kota_depart_id
                line.ke_kota_id = line.up_country_id.kota_tujuan_id

    @api.onchange('waktu_akomodasi')
    def _onchange_waktu_akomodasi(self):
        if self.waktu_akomodasi:
            self.tgl_check_depart = self.waktu_akomodasi.date()

    @api.depends('transportasi', 'dt_start', 'dt_end')
    def _compute_time_info_display(self):
        for record in self:
            value = ""
            if record.dt_start:
                if record.transportasi == 'hotel':
                    if record.dt_end:
                        delta = (
                                record.dt_end.date()
                                - record.dt_start.date()
                        )
                        days = delta.days
                        value = f"{days + 1} Hari {days} Malam"
                    else:
                        value = "Set Tanggal Check-out"

                else:
                    start_t = fields.Datetime.context_timestamp(
                        record,
                        record.dt_start
                    ).strftime('%H:%M')

                    end_t = (
                        fields.Datetime.context_timestamp(
                            record,
                            record.dt_end
                        ).strftime('%H:%M')
                        if record.dt_end else "??"
                    )
                    value = f"{start_t} - {end_t}"
            record.time_info_display = value

    def action_open_payment_wizard(self):
        self.ensure_one()

        if not self._origin.id:
            raise exceptions.UserError(
                "Silakan save dokumen terlebih dahulu."
            )

        existing_lines = []

        for schedule in self.payment_schedule_ids:
            existing_lines.append((0, 0, {
                'date_payment': schedule.date_payment,
                'amount_percentage': schedule.amount_percentage,
                'amount': schedule.amount,
            }))

        return {
            'name': 'Atur Termin Pembayaran',
            'type': 'ir.actions.act_window',
            'res_model': 'usulan.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_up_country_line_id': self.id,
                'default_total_amount': 0,
                'default_wizard_line_ids': existing_lines,
            }
        }

    def action_open_time_wizard(self):
        return {
            'name': 'Set Detail Waktu',
            'type': 'ir.actions.act_window',
            'res_model': 'akomodasi.uc.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_line_id': self.id,
                'default_transportasi': self.transportasi,
                'default_dt_start': self.dt_start,
                'default_dt_end': self.dt_end,
            }
        }

class UangLainnyaLine(models.Model):
    _name = 'uang.lainnya.line'

    up_country_id = fields.Many2one(
        'usulan.up.country'
    )

    keterangan = fields.Char()
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )
    tanggal = fields.Date()
    jenis_id = fields.Many2one('jenis.transportasi')
    dari = fields.Char()
    ke = fields.Char()
    amount = fields.Monetary(currency_field='currency_id')

class RencanaKerjaLine(models.Model):
    _name = 'rencana.kerja.line'

    up_country_id = fields.Many2one(
        'usulan.up.country'
    )

    jenis_id = fields.Many2one(
        'jenis.rencana.kerja',
        string="Jenis"
    )

    tipe_visit_id = fields.Many2one(
        'tipe.visit',
        string="Tipe Visit"
    )

    tujuan_id = fields.Many2one(
        'tujuan.rencana.kerja',
        string="Tujuan"
    )

    deskripsi = fields.Text()
    tanggal = fields.Datetime(string="Tanggal")