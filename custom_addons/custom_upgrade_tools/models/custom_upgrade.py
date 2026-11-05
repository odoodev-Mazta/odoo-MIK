import logging
import os
from datetime import timedelta

import psycopg2

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.modules.loading import reset_modules_state
from odoo.modules.module import get_module_path
from odoo.modules.registry import Registry

_logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3   # percobaan upgrade yang benar-benar berjalan lalu gagal karena database
RETRY_DELAY = 5    # detik, jeda sebelum mencoba ulang
# Odoo menolak mulai upgrade selama scheduled action atau operasi modul lain berjalan.
# Itu bukan percobaan: tunggu sampai selesai, paling lama MAX_WAITS x WAIT_DELAY.
MAX_WAITS = 12
WAIT_DELAY = 10
# Status 'to upgrade' yang lebih lama dari ini dianggap tertinggal (proses terputus).
STALE_MINUTES = 10
# Satu upgrade dalam satu waktu, juga bila halaman dibuka di dua tab.
LOCK_KEY = 'custom_upgrade_tools'


class CustomUpgradeRun(models.Model):
    _name = 'custom.upgrade.run'
    _description = 'Riwayat Upgrade Modul Custom'
    _order = 'id desc'

    name = fields.Char(required=True, default=lambda self: _('Upgrade %s', fields.Datetime.now()))
    user_id = fields.Many2one('res.users', string='Dijalankan oleh', default=lambda self: self.env.user)
    state = fields.Selection([
        ('running', 'Berjalan'),
        ('done', 'Selesai'),
        ('failed', 'Ada yang Gagal'),
    ], default='running', required=True)
    date_start = fields.Datetime(default=fields.Datetime.now)
    date_end = fields.Datetime()
    line_ids = fields.One2many('custom.upgrade.run.line', 'run_id')

    def _check_admin(self):
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Hanya Administrator yang bisa mengupgrade modul.'))

    @api.model
    def _get_custom_modules(self):
        """Modul terpasang yang foldernya sama dengan modul ini (custom_addons)."""
        root = os.path.normcase(os.path.dirname(get_module_path('custom_upgrade_tools')))
        modules = self.env['ir.module.module'].search([
            ('state', '=', 'installed'),
            ('name', '!=', 'custom_upgrade_tools'),
        ])
        return modules.filtered(
            lambda mod: (path := get_module_path(mod.name, display_warning=False))
            and os.path.normcase(os.path.dirname(path)) == root
        )

    @api.model
    def _sort_by_dependency(self, modules):
        """Modul yang menjadi dependensi diupgrade lebih dulu."""
        by_name = {mod.name: mod for mod in modules}
        pending = {
            mod.name: set(mod.dependencies_id.mapped('name')) & by_name.keys()
            for mod in modules
        }
        ordered = []
        while pending:
            ready = sorted(name for name, deps in pending.items() if deps <= set(ordered))
            ordered += ready or sorted(pending)  # 'or' hanya untuk dependensi melingkar
            for name in ready or list(pending):
                pending.pop(name)
        return [by_name[name] for name in ordered]

    # ─── Dipanggil dari dashboard ───────────────────────────────────────────

    @api.model
    def action_start(self, module_ids=None):
        """Mulai upgrade baru, atau lanjutkan yang belum selesai.

        module_ids: hanya modul custom yang dipilih; kosong = semua modul custom.
        """
        self._check_admin()
        run = self.search([('state', '=', 'running')], limit=1)
        if not run:
            custom = self._get_custom_modules()
            modules = custom.filtered(lambda mod: mod.id in module_ids) if module_ids else custom
            if not modules:
                raise UserError(_('Pilih minimal satu modul untuk diupgrade.'))
            modules = self._sort_by_dependency(modules)
            names = ', '.join(mod.name for mod in modules[:3]) + ('…' if len(modules) > 3 else '')
            run = self.create({
                'name': _('Upgrade %(n)s modul: %(names)s', n=len(modules), names=names)
                if module_ids else _('Upgrade semua modul (%s)', fields.Datetime.now()),
                'line_ids': [
                    (0, 0, {'module_id': mod.id, 'sequence': index})
                    for index, mod in enumerate(modules)
                ],
            })
        return run.id

    def action_retry_failed(self):
        self._check_admin()
        self.line_ids.filtered(lambda line: line.state in ('failed', 'skipped')).write({
            'state': 'pending', 'attempts': 0, 'waits': 0, 'error': False,
        })
        self.write({'state': 'running', 'date_end': False})
        return True

    def action_process_next(self):
        """Upgrade satu modul berikutnya. Dashboard memanggil ini berulang sampai selesai.

        Mengembalikan {'wait': detik} bila dashboard perlu menunggu sebelum lanjut.
        """
        self.ensure_one()
        self._check_admin()
        cr = self.env.cr
        cr.execute("SELECT pg_try_advisory_lock(hashtext(%s))", [LOCK_KEY])
        if not cr.fetchone()[0]:
            return {'wait': RETRY_DELAY, 'busy': True}
        try:
            if self.state != 'running':
                return {}
            self._reset_stale_module_states()
            # Baris yang tertinggal 'running' (tab ditutup / server restart) diulang.
            line = self.line_ids.filtered(lambda l: l.state in ('pending', 'running'))[:1]
            if not line:
                self._finish()
                return {}
            return line._run_upgrade()
        finally:
            cr.execute("SELECT pg_advisory_unlock(hashtext(%s))", [LOCK_KEY])

    def _reset_stale_module_states(self):
        """Pulihkan modul yang macet di 'to upgrade' karena proses sebelumnya terputus."""
        limit = fields.Datetime.now() - timedelta(minutes=STALE_MINUTES)
        stale = self.env['ir.module.module'].search_count([
            ('state', 'in', ('to upgrade', 'to install', 'to remove')),
            ('write_date', '<', limit),
        ])
        if stale:
            _logger.warning("%s modul macet di status 'to ...', direset", stale)
            reset_modules_state(self.env.cr.dbname)

    def _finish(self):
        problem = self.line_ids.filtered(lambda line: line.state in ('failed', 'skipped'))
        self.write({'state': 'failed' if problem else 'done', 'date_end': fields.Datetime.now()})

    @api.model
    def get_dashboard_data(self, run_id=None):
        self._check_admin()
        run = self.browse(run_id) if run_id else self.search([], limit=1)
        history = self.search([], limit=10)
        return {
            'run': run._dashboard_values() if run else False,
            'history': [{
                'id': rec.id,
                'name': rec.name,
                'state': rec.state,
                'user': rec.user_id.name,
                'date_start': fields.Datetime.to_string(rec.date_start),
            } for rec in history],
            'module_count': len(self._get_custom_modules()),
            'modules': [{
                'id': mod.id,
                'name': mod.name,
                'title': mod.shortdesc or mod.name,
                'version': mod.installed_version or mod.latest_version or '',
            } for mod in self._get_custom_modules().sorted('name')],
        }

    def _dashboard_values(self):
        self.ensure_one()
        lines = self.line_ids
        return {
            'id': self.id,
            'name': self.name,
            'state': self.state,
            'user': self.user_id.name,
            'date_start': fields.Datetime.to_string(self.date_start),
            'date_end': fields.Datetime.to_string(self.date_end),
            'total': len(lines),
            'done': len(lines.filtered(lambda line: line.state == 'done')),
            'failed': len(lines.filtered(lambda line: line.state == 'failed')),
            'skipped': len(lines.filtered(lambda line: line.state == 'skipped')),
            'lines': [{
                'id': line.id,
                'module': line.module_id.name,
                'title': line.module_id.shortdesc,
                'state': line.state,
                'attempts': line.attempts,
                'error': line.error,
                'duration': line.duration,
            } for line in lines],
        }


class CustomUpgradeRunLine(models.Model):
    _name = 'custom.upgrade.run.line'
    _description = 'Modul dalam Upgrade'
    _order = 'sequence, id'

    run_id = fields.Many2one('custom.upgrade.run', required=True, ondelete='cascade')
    module_id = fields.Many2one('ir.module.module', required=True, ondelete='cascade')
    sequence = fields.Integer()
    state = fields.Selection([
        ('pending', 'Menunggu'),
        ('running', 'Berjalan'),
        ('done', 'Selesai'),
        ('failed', 'Gagal'),
        ('skipped', 'Ditunda'),
    ], default='pending', required=True)
    attempts = fields.Integer()
    waits = fields.Integer(help="Berapa kali menunggu Odoo selesai menjalankan proses lain.")
    error = fields.Text()
    date_start = fields.Datetime()
    date_end = fields.Datetime()
    duration = fields.Integer(string='Durasi (detik)')

    def _run_upgrade(self):
        self.ensure_one()
        dbname, uid, line_id = self.env.cr.dbname, self.env.uid, self.id
        self.write({
            'state': 'running',
            'attempts': self.attempts + 1,
            'date_start': fields.Datetime.now(),
            'error': False,
        })
        self.env.cr.commit()

        started = []

        def upgrade_this_module_only(modules):
            started.append(True)
            modules.button_upgrade()
            # button_upgrade ikut menandai modul turunan; modul itu punya gilirannya sendiri.
            modules.search([
                ('state', '=', 'to upgrade'), ('id', 'not in', modules.ids),
            ]).write({'state': 'installed'})

        error = None
        try:
            self.module_id._button_immediate_function(upgrade_this_module_only)
        except Exception as exc:  # noqa: BLE001 - semua kegagalan dicatat di baris
            _logger.exception("Upgrade modul %s gagal", self.module_id.name)
            self.env.cr.rollback()
            error = exc

        # Registry sudah diganti (berhasil) atau dibangun ulang (gagal): pakai cursor baru.
        with Registry(dbname).cursor() as new_cr:
            env = api.Environment(new_cr, uid, {})
            return env['custom.upgrade.run.line'].browse(line_id)._record_result(
                error, started=bool(started))

    def _record_result(self, error, started):
        now = fields.Datetime.now()
        duration = int((now - self.date_start).total_seconds()) if self.date_start else 0
        if error is None:
            self.write({'state': 'done', 'date_end': now, 'duration': duration})
            return {}

        message = f"{type(error).__name__}: {error}"
        if not started and self.waits < MAX_WAITS:
            # Odoo menolak mulai: scheduled action / operasi modul lain sedang berjalan.
            self.write({
                'state': 'pending',
                'attempts': self.attempts - 1,
                'waits': self.waits + 1,
                'error': _('Menunggu Odoo selesai menjalankan proses lain (%(n)s/%(max)s).\n%(msg)s',
                           n=self.waits + 1, max=MAX_WAITS, msg=message),
            })
            return {'wait': WAIT_DELAY}
        if started and isinstance(error, psycopg2.OperationalError) and self.attempts < MAX_ATTEMPTS:
            self.write({
                'state': 'pending',
                'error': _('Percobaan %(n)s gagal sementara, dicoba lagi.\n%(msg)s',
                           n=self.attempts, msg=message),
            })
            return {'wait': RETRY_DELAY}

        self.write({'state': 'failed', 'error': message, 'date_end': now, 'duration': duration})
        # Modul yang bergantung pada modul gagal ditunda.
        dependents = self.module_id.downstream_dependencies()
        self.run_id.line_ids.filtered(
            lambda line: line.state == 'pending' and line.module_id in dependents
        ).write({
            'state': 'skipped',
            'error': _('Ditunda karena %s gagal diupgrade.', self.module_id.name),
        })
        return {}
