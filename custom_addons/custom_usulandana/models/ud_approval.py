from odoo import models,fields,api, tools

class UsulanDanaApproval(models.Model):
    _name = 'usulan.dana.approval'
    _description = 'Approval Usulan Dana'
    _auto = False
    _inherit = ['mail.activity.mixin', 'mail.thread']

    name = fields.Char(string='No Usulan', readonly=True)
    date_requested = fields.Datetime(string='Tgl Diajukan', readonly=True)
    department_id = fields.Many2one('hr.department', string='Departemen', readonly=True)
    description = fields.Text(string='Keterangan', readonly=True)
    amount = fields.Float(string='Nilai Usulan', readonly=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('to_approve', 'Menunggu Approval'),
        ('approve', 'Approved'),
        ('reject', 'Ditolak'),
        ('cancel', 'Cancelled')
    ], string='Status', readonly=True)

    # Field sistematis untuk menentukan arah klik (Redirection)
    source_model = fields.Selection([
        ('usulan.usulan.dana', 'Usulan Dana'),
        ('usulan.up.country', 'Up Country')
    ], string='Tipe Dokumen', readonly=True)
    source_id = fields.Integer(string='ID Asli Dokumen', readonly=True)

    req_coo = fields.Boolean(string='Need COO', compute='_compute_approval_requirements', store=True)
    req_ceo = fields.Boolean(string='Need CEO', compute='_compute_approval_requirements', store=True)

    def init(self):
        # 1. Hancurkan tabel/view lama hingga ke akar-akarnya
        self.env.cr.execute("""
            SELECT relkind FROM pg_class WHERE relname = %s
        """, (self._table,))
        result = self.env.cr.fetchone()

        if result and result[0] == 'r':
            self.env.cr.execute("DROP TABLE IF EXISTS %s CASCADE" % self._table)
        elif result and result[0] == 'v':
            self.env.cr.execute("DROP VIEW IF EXISTS %s CASCADE" % self._table)

        # 2. Buat ulang View-nya
        self.env.cr.execute("""
            CREATE VIEW %s AS (
                SELECT 
                (ud.id * 10) + 1 AS id,
                ud.name,
                ud.date_submitted AS date_requested,
                ud.department_id,
                ud.description,
                ud.amount_total AS amount,
                ud.state,
                EXISTS (SELECT 1 FROM ir_attachment WHERE res_model = 'usulan.dana' AND res_id = ud.id) AS has_attachment,
                'usulan.usulan.dana' AS source_model, --
                ud.id AS source_id,
                req_coo,
                req_ceo
            FROM usulan_usulan_dana ud
    
            UNION ALL
    
            SELECT 
                (up.id * 10) + 2 AS id,
                up.name,
                up.date_submitted AS date_requested,
                up.department_id,
                NULL::text AS description,
                up.amount AS amount,
                up.state,
                EXISTS (SELECT 1 FROM ir_attachment WHERE res_model = 'usulan.up.country' AND res_id = up.id) AS has_attachment,
                'usulan.up.country' AS source_model, --
                up.id AS source_id,
                FALSE AS req_coo,
                FALSE AS req_ceo
            FROM usulan_up_country up
        )
    """ % (self._table,))

    def action_buka_dokumen(self):
        """ Fungsi ajaib untuk melompat ke form asli saat baris di-klik """
        self.ensure_one()
        return {
            'name': 'Detail Dokumen',
            'type': 'ir.actions.act_window',
            'res_model': self.source_model,
            'res_id': self.source_id,
            'view_mode': 'form',
            'target': 'current',
        }