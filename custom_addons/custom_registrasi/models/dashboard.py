from odoo import models, api
from datetime import date, timedelta


class RegistrasiDashboard(models.AbstractModel):
    _name = 'registrasi.dashboard'
    _description = 'Dashboard Registrasi'

    @api.model
    def get_dashboard_data(self):
        today = date.today()
        soon = today + timedelta(days=90)

        # ── NIE (registrasi.produk) ───────────────────────────────────────
        NIE = self.env['registrasi.produk']
        nie_total   = NIE.search_count([])
        nie_draft   = NIE.search_count([('state', '=', 'draft')])
        nie_process = NIE.search_count([('state', 'in', [
            'form_request', 'ro_drafting', 'submitted',
            'payment_request', 'payment_verification', 'bpom_review',
        ])])
        nie_issued  = NIE.search_count([('state', '=', 'nie_issued')])
        nie_failed  = NIE.search_count([('state', '=', 'failed')])
        nie_expired = self.env['registrasi.produk.line'].search_count([
            ('nie_expired_date', '!=', False),
            ('nie_expired_date', '<', today),
        ])

        # ── HALAL (halal.registrasi) ──────────────────────────────────────
        HAL = self.env['halal.registrasi']
        hal_total   = HAL.search_count([])
        hal_aktif   = HAL.search_count([('state', '=', 'sertifikat_terbit')])
        hal_process = HAL.search_count([('state', 'in', [
            'draft', 'pengajuan', 'verifikasi_internal',
            'submitted_lembaga', 'audit_halal', 'menunggu_keputusan',
        ])])
        hal_soon    = HAL.search_count([
            ('tanggal_expired', '>=', today),
            ('tanggal_expired', '<=', soon),
            ('state', '=', 'sertifikat_terbit'),
        ])
        hal_expired = HAL.search_count([('state', '=', 'kadaluarsa')])
        hal_ditolak = HAL.search_count([('state', '=', 'ditolak')])

        # ── BRAND (registrasi.brand) ──────────────────────────────────────
        BRD = self.env['registrasi.brand']
        brd_total    = BRD.search_count([])
        brd_draft    = BRD.search_count([('state', '=', 'draft')])
        brd_process  = BRD.search_count([('state', 'in', [
            'sub_company_activation', 'regulatory_submit', 'bpom_verification',
        ])])
        brd_approved = BRD.search_count([('state', '=', 'approved')])
        brd_rejected = BRD.search_count([('state', '=', 'rejected')])

        # ── STATE LABEL MAP ───────────────────────────────────────────────
        STATE_LABEL_NIE = {
            'draft':                ('Draft',                'secondary'),
            'form_request':         ('Form Request',         'warning'),
            'ro_drafting':          ('RO Drafting',          'info'),
            'submitted':            ('Submitted',            'primary'),
            'payment_request':      ('Payment Request',      'warning'),
            'payment_verification': ('Payment Verification', 'info'),
            'bpom_review':          ('BPOM Review',          'primary'),
            'nie_issued':           ('NIE Issued',           'success'),
            'failed':               ('Failed',               'danger'),
        }
        STATE_LABEL_HALAL = {
            'draft':                ('Draft',                'secondary'),
            'pengajuan':            ('Pengajuan',            'warning'),
            'verifikasi_internal':  ('Verifikasi Internal',  'info'),
            'submitted_lembaga':    ('Submitted',            'primary'),
            'audit_halal':          ('Audit Halal',          'primary'),
            'menunggu_keputusan':   ('Menunggu Keputusan',   'warning'),
            'sertifikat_terbit':    ('Aktif',                'success'),
            'ditolak':              ('Ditolak',              'danger'),
            'kadaluarsa':           ('Expired',              'danger'),
        }
        STATE_LABEL_BRAND = {
            'draft':                  ('Draft',              'secondary'),
            'sub_company_activation': ('Aktivasi',           'warning'),
            'regulatory_submit':      ('Regulatory Submit',  'info'),
            'bpom_verification':      ('BPOM Verification',  'primary'),
            'approved':               ('Approved',           'success'),
            'rejected':               ('Rejected',           'danger'),
        }

        # ── TABLE NIE ─────────────────────────────────────────────────────
        table_nie = []

        for r in NIE.search([]):

            label, color = STATE_LABEL_NIE.get(
                r.state,
                (r.state, 'secondary')
            )

            for line in r.product_line_ids:
                table_nie.append({
                    'id': r.id,
                    'line_id': line.id,
                    'name': r.name,
                    'product_name': (
                        line.product_template_id.name
                        if line.product_template_id
                        else '-'
                    ),
                    'official_name': (
                            line.official_product_name
                            or '-'
                    ),
                    'client': (
                        r.client_id.name
                        if r.client_id
                        else '-'
                    ),
                    'state_label': label,
                    'state_color': color,
                    'nie_number': (
                            line.nie_number
                            or '-'
                    ),
                })

        # ── TABLE HALAL ───────────────────────────────────────────────────
        table_halal = []
        for r in HAL.search([]):
            label, color = STATE_LABEL_HALAL.get(r.state, (r.state, 'secondary'))
            table_halal.append({
                'id':              r.id,
                'name':            r.name,
                'product_name': ', '.join(
                    r.product_line_ids.mapped(
                        'product_template_id.name'
                    )
                ) or '-',
                'client':          r.client_id.name if r.client_id else '-',
                'state_label':     label,
                'state_color':     color,
                'tanggal_expired': str(r.tanggal_expired) if r.tanggal_expired else '-',
            })

        # ── TABLE BRAND ───────────────────────────────────────────────────
        table_brand = []
        for r in BRD.search([]):
            label, color = STATE_LABEL_BRAND.get(r.state, (r.state, 'secondary'))
            table_brand.append({
                'id':          r.id,
                'name':        r.name,
                'brand_name':  r.brand_name or '-',
                'client':      r.client_id.name if r.client_id else '-',
                'state_label': label,
                'state_color': color,
                'brand_owner': r.brand_owner or '-',
            })

        # ── RETURN ────────────────────────────────────────────────────────
        return {
            'nie': {
                'total':   nie_total,
                'draft':   nie_draft,
                'process': nie_process,
                'issued':  nie_issued,
                'failed':  nie_failed,
                'expired': nie_expired,
            },
            'halal': {
                'total':   hal_total,
                'aktif':   hal_aktif,
                'process': hal_process,
                'soon':    hal_soon,
                'expired': hal_expired,
                'ditolak': hal_ditolak,
            },
            'brand': {
                'total':    brd_total,
                'draft':    brd_draft,
                'process':  brd_process,
                'approved': brd_approved,
                'rejected': brd_rejected,
            },
            'table_nie':   table_nie,
            'table_halal': table_halal,
            'table_brand': table_brand,
        }