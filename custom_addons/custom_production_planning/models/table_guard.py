from odoo import models
from odoo.tools.sql import table_exists


class HistoryTableGuard(models.AbstractModel):
    """Buat tabel model bila belum ada. Registry bisa dimuat dengan kode baru sebelum modul di-upgrade (mis. saat
    build), dan tanpa ini muncul ERROR 'Model ... has no table' di log."""
    _name = "history.table.guard"
    _description = "Pengaman Tabel Model Riwayat"

    def init(self):
        if not table_exists(self.env.cr, self._table):
            self._auto_init()
