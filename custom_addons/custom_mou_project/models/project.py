from datetime import timedelta

from odoo import _, api, fields, models
from odoo.fields import Domain
from odoo.exceptions import AccessError

# Sama dengan 9 tahapan di Tracking MOU.
STAGES = [
    ('mou', '1. MOU'),
    ('regfee', '2. Biaya Registrasi'),
    ('dp', '3. DP'),
    ('regis', '4. Registrasi'),
    ('buy', '5. Pengadaan'),
    ('prod', '6. Produksi'),
    ('qc', '7. QC'),
    ('bp', '8. BP'),
    ('ship', '9. Delivery'),
]
# Tagihan MOU (mou.setup) -> tahap, dan awalan nama field tanggalnya.
SETUP_STAGE = {
    'biaya_registrasi': ('regfee', 'reg'),
    'dp': ('dp', 'dp'),
    'nie': ('regis', 'nie'),
    'pengadaan': ('buy', 'peng'),
    'bp': ('bp', 'bp'),
}


def _dt(value):
    """date / datetime / False -> datetime / False."""
    return fields.Datetime.to_datetime(value) if value else False


class ProjectProject(models.Model):
    _inherit = 'project.project'

    mou_id = fields.Many2one('draft.maklon', string="MOU", index=True, copy=False)

    # ------------------------------------------------------------------ tombol
    def action_view_tasks(self):
        """Semua jalur membuka task Project (kartu Project, tombol Tasks, tombol di form MOU) lewat sini.
        Untuk Project MOU: tanpa filter 'Open' supaya task selesai ikut terlihat, dan terbuka langsung di SO terbaru
        (chip 'Per SO'). Ganti SO dengan mengetik / memilih di kolom pencarian."""
        action = super().action_view_tasks()
        if self.mou_id:
            context = dict(action['context'])
            context.pop('search_default_open_tasks', None)
            context['mou_so_mou_id'] = self.mou_id.id
            order = self.env['sale.order'].search(
                [('mou_id', '=', self.mou_id.id), ('state', 'not in', ('draft', 'cancel'))], order='id desc', limit=1)
            if order:
                context['search_default_mou_so_scope'] = order.id
            action['context'] = context
        return action

    def action_sync_from_mou(self):
        for project in self.filtered('mou_id'):
            project._sync_from_mou()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Project diperbarui"),
                'message': _("Task dan tanggal sudah disamakan dengan dokumen MOU, PR, PO, Plan Produksi, QC, dan Delivery."),
                'type': 'success',
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    def action_delete_project(self):
        """Hapus Project beserta task-nya. Khusus Administrator. Dokumen sumber tidak ikut terhapus;
        Project bisa dibuat lagi dari tombol Project di form MOU."""
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_("Hanya Administrator yang boleh menghapus Project."))
        self.sudo().unlink()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Projects"),
            'res_model': 'project.project',
            'view_mode': 'kanban,list,form',
            'target': 'main',
        }

    # ------------------------------------------------------------------ task
    def _stage_for(self, key):
        self.ensure_one()
        name = dict(STAGES)[key]
        sequence = [k for k, _n in STAGES].index(key) + 1
        stage = self.type_ids.filtered(lambda s: s.name == name)[:1]
        if not stage:
            stage = self.env['project.task.type'].create({
                'name': name, 'sequence': sequence, 'project_ids': [(4, self.id)],
            })
        elif stage.sequence != sequence:
            stage.sequence = sequence
        return stage

    def _upsert_task(self, key, name, stage_key, begin, deadline, done=False, order=None, level=False):
        """Buat / perbarui satu task berdasarkan kunci dokumen sumber. Tanggal selalu mengikuti dokumen."""
        self.ensure_one()
        Task = self.env['project.task'].with_context(mail_notrack=True, tracking_disable=True)
        begin = _dt(begin) or _dt(deadline) or fields.Datetime.now()
        deadline = _dt(deadline) or begin + timedelta(days=1)
        if deadline < begin:
            deadline = begin + timedelta(days=1)
        vals = {
            'name': name,
            'stage_id': self._stage_for(stage_key).id,
            'planned_date_begin': begin,
            'date_deadline': deadline,
            'mou_sale_order_id': order.id if order else False,
            'mou_level': level,
        }
        task = Task.search([('project_id', '=', self.id), ('sync_key', '=', key)], limit=1)
        if task:
            if done and task.state != '1_done':
                vals['state'] = '1_done'
            task.write(vals)
        else:
            if done:
                vals['state'] = '1_done'
            task = Task.create(dict(vals, project_id=self.id, sync_key=key))
        return task

    # ------------------------------------------------------------------ sinkron
    def _sync_from_mou(self):
        """Isi Project (satu MOU) dengan 9 tahap seperti Tracking MOU, tanggal dari dokumen aslinya.

        Tahap tingkat MOU (MOU, Biaya Registrasi, DP, Registrasi, BP) tampil untuk semua SO. Dokumen per SO
        (PR, PO, Plan, QC, Delivery) dibuat sebagai task yang menunjuk SO-nya; SO PR / PO dibaca dari baris
        produknya (satu PR / PO bisa memuat banyak SO), sama dengan Tracking MOU. Dokumen yang belum punya SO
        hanya tampil bila tidak ada SO yang dipilih."""
        self.ensure_one()
        env, mou = self.env, self.mou_id
        day = timedelta(days=1)
        kept = env['project.task']
        no_so = env['sale.order']
        active_orders = env['sale.order'].search([('mou_id', '=', mou.id), ('state', 'not in', ('draft', 'cancel'))])
        # MOU dengan satu SO aktif saja: dokumen tanpa SO pasti miliknya (sama dengan Tracking MOU).
        only_so = active_orders if len(active_orders) == 1 else no_so

        def put(key, name, stage, begin, deadline, done=False, sos=None, level=False):
            nonlocal kept
            if level:
                kept |= self._upsert_task(key, name, stage, begin, deadline, done=done, level=True)
                return
            for order in (sos or only_so or [no_so]):
                kept |= self._upsert_task('%s:%s' % (key, order.id or 0), name, stage, begin, deadline,
                                          done=done, order=order)

        # 1. MOU
        if mou.tgl_start or mou.tgl_draft:
            start = mou.tgl_start or mou.tgl_draft
            until = ' (berlaku s/d %s)' % mou.tgl_end.strftime('%d %b %Y') if mou.tgl_end else ''
            put('mou:%s' % mou.id, _("MOU disahkan%s") % until, 'mou', start, _dt(start) + day,
                done=mou.state == 'mou', level=True)

        # 2, 3, 8. Tagihan MOU: jatuh tempo = estimasi, tanggal bayar = selesai.
        labels = dict(env['mou.setup']._fields['state'].selection)
        for setup in env['mou.setup'].search([('mou_id', '=', mou.id)]):
            stage, pre = SETUP_STAGE.get(setup.state, (None, None))
            if not stage:
                continue
            due, paid = setup[pre + '_due_date'], setup[pre + '_payment_date']
            begin = setup.date or due or paid
            if begin:
                put('setup:%s' % setup.id, _("Pembayaran %s") % labels.get(setup.state, setup.state), stage,
                    begin, due or paid or _dt(begin) + 7 * day, done=bool(paid), level=True)

        # 4. Registrasi: brand, produk (BPOM), halal, desain.
        for brand in env['registrasi.brand'].search([('mou_id', '=', mou.id)]):
            put('regbrand:%s' % brand.id, _("Registrasi Brand: %s") % (brand.brand_name or brand.name), 'regis',
                brand.create_date, brand.verification_deadline or brand.submit_deadline,
                done=brand.state == 'approved', level=True)
        for prod in env['registrasi.produk'].search([('mou_id', '=', mou.id)]):
            put('regprod:%s' % prod.id, _("Registrasi Produk (BPOM): %s") % prod.name, 'regis',
                prod.create_date, prod.bpom_review_deadline or prod.submit_deadline,
                done=prod.state == 'nie_issued', level=True)
        for halal in env['halal.registrasi'].search([('mou_id', '=', mou.id)]):
            put('halal:%s' % halal.id, _("Sertifikasi Halal: %s") % halal.display_name, 'regis',
                halal.tanggal_pengajuan or halal.create_date, halal.target_selesai or halal.tanggal_terbit,
                done=halal.state == 'sertifikat_terbit', level=True)
        for design in env['design.usulan'].search([('mou_id', '=', mou.id)]):
            begin = design.date or design.create_date
            put('design:%s' % design.id, _("Desain: %s") % design.display_name, 'regis', begin,
                design.date_done or _dt(begin) + 14 * day, done=design.state == 'done', level=True)

        # 5. Pengadaan: PR, PO (per baris barang), Usulan Dana.
        prs = env['purchase.request'].search(['|', ('mou_id', '=', mou.id), ('bulk_line_ids.mou_id', '=', mou.id)])

        def pr_sos(pr):
            if pr.is_bulk_purchase:
                return no_so
            lines = pr.request_line_ids.filtered(lambda l: not l.display_type and l.product_id)
            return lines.mapped(lambda l: l.sale_order_id or pr.sale_order_id)

        for pr in prs:
            begin = pr.date_usulan or pr.create_date
            put('pr:%s' % pr.id, _("Pengajuan %s") % pr.name, 'buy', begin,
                pr.estimated_date or _dt(begin) + 7 * day, done=pr.state == 'pr', sos=pr_sos(pr))

        pos = env['purchase.order'].search([
            '&', ('state', '!=', 'cancel'),
            '|', '|', ('mou_id', '=', mou.id), ('purchase_request_id', 'in', prs.ids),
            ('customer_line_ids.request_id', 'in', prs.ids)], order='date_order, id')
        for po in pos:
            sos = po.customer_line_ids.mapped(lambda cl: cl.sale_order_id or cl.request_id.sale_order_id)
            if not sos:
                for rq in po.purchase_request_ids | po.purchase_request_id:
                    sos |= pr_sos(rq)
            sos = sos or po.sale_order_id
            for line in po.order_line.filtered(lambda l: not l.display_type):
                label = line.product_id.display_name or line.name
                put('pol:%s' % line.id, _("Beli: %s (%s)") % (label, po.name), 'buy', po.date_order,
                    line.date_planned or po.date_planned, done=po.receipt_status == 'full', sos=sos)

        if 'usulan.usulan.dana' in env:
            usulans = env['usulan.usulan.dana'].search([
                '|', '|', '|', ('purchase_order_ids.mou_id', '=', mou.id),
                ('purchase_order_ids.customer_line_ids.mou_id', '=', mou.id),
                ('line_ids.mou_id', '=', mou.id), ('id', 'in', prs.usulan_dana_id.ids),
                ('state', '!=', 'cancel')], order='tgl_usulan, id')
            for ud in usulans:
                pos_ud = ud.purchase_order_ids or ud.purchase_order_id
                sos = pos_ud.sale_order_id | prs.filtered(lambda p: p.usulan_dana_id == ud).sale_order_id
                put('ud:%s' % ud.id, _("Usulan Dana: %s") % ud.name, 'buy', ud.tgl_usulan,
                    _dt(ud.tgl_usulan) + 7 * day if ud.tgl_usulan else None,
                    done=ud.status_payment == 'paid', sos=sos)

        # 6. Produksi: Plan Produksi.
        for plan in env['mrp.production.plan'].search(
                [('mou_id', '=', mou.id), ('state', '!=', 'cancel')], order='planned_start, id'):
            put('plan:%s' % plan.id, _("Produksi: %s") % plan.name, 'prod', plan.planned_start,
                plan.planned_end, done=plan.state == 'done', sos=plan.sale_order_id)

        # 7. QC.
        if 'production.qc.schedule' in env:
            for sched in env['production.qc.schedule'].search(
                    [('production_id.production_plan_id.sale_order_id.mou_id', '=', mou.id)]):
                begin = sched.inspection_date or sched.create_date
                put('qc:%s' % sched.id, _("QC: %s") % sched.name, 'qc', begin, _dt(begin) + day,
                    done=sched.state == 'done', sos=sched.production_id.production_plan_id.sale_order_id)

        # 9. Delivery.
        orders = env['sale.order'].search([('mou_id', '=', mou.id), ('state', 'not in', ('draft', 'cancel'))])
        for pick in env['stock.picking'].search([
                ('sale_id', 'in', orders.ids), ('picking_type_code', '=', 'outgoing'),
                ('state', '!=', 'cancel')], order='scheduled_date, id'):
            put('pick:%s' % pick.id, _("Pengiriman %s") % pick.name, 'ship', pick.scheduled_date,
                pick.date_done or pick.scheduled_date, done=pick.state == 'done', sos=pick.sale_id)

        # Task hasil sinkron yang dokumennya sudah tidak ada / pindah SO dibersihkan. Task buatan manual tidak disentuh.
        env['project.task'].search([
            ('project_id', '=', self.id), ('sync_key', '!=', False), ('id', 'not in', kept.ids)]).unlink()
        # Kolom tahap lama yang kosong (dari versi sebelumnya) dirapikan.
        valid = {name for _key, name in STAGES}
        for stage in self.type_ids.filtered(lambda s: s.name not in valid):
            if not env['project.task'].with_context(active_test=False).search_count([('stage_id', '=', stage.id)]):
                stage.write({'project_ids': [(3, self.id)]})


class ProjectTask(models.Model):
    _inherit = 'project.task'

    mou_sale_order_id = fields.Many2one('sale.order', string="Sales Order (MOU)", index=True, copy=False)
    mou_level = fields.Boolean(
        string="Tahap Tingkat MOU", copy=False,
        help="Task milik MOU (MOU, pembayaran, registrasi), bukan milik satu Sales Order: tampil di semua SO.")
    sync_key = fields.Char(string="Kunci Dokumen Sumber", index=True, copy=False, readonly=True,
                           help="Penanda dokumen asal task ini. Dipakai untuk sinkronisasi.")
    mou_so_scope = fields.Many2one(
        'sale.order', string="Per SO", compute='_compute_mou_so_scope', search='_search_mou_so_scope',
        help="Pilih Sales Order untuk melihat seluruh alurnya: task milik SO itu ditambah task tingkat MOU.")

    @api.depends('mou_sale_order_id')
    def _compute_mou_so_scope(self):
        for task in self:
            task.mou_so_scope = task.mou_sale_order_id

    def _search_mou_so_scope(self, operator, value):
        if isinstance(value, Domain):
            orders = self.env['sale.order'].search(value)  # Odoo 19: teks yang diketik dikirim sebagai domain
        elif isinstance(value, str):
            orders = self.env['sale.order'].search([('name', 'ilike', value)])
        else:
            ids = [value] if isinstance(value, int) else list(value or [])
            orders = self.env['sale.order'].browse(ids).exists()
        return ['|', ('mou_sale_order_id', 'in', orders.ids), ('mou_level', '=', True)]
