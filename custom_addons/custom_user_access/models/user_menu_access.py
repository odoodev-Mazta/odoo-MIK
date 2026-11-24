from collections import defaultdict

from odoo import api, fields, models, tools
from odoo.exceptions import AccessError
from odoo.tools.sql import table_exists

PERMS = ("view", "create", "write", "unlink", "approve")
MODEL_MODES = {"create": "create", "write": "write", "unlink": "unlink"}


class UserMenuAccess(models.Model):
    """Pembatasan akses per user per menu, di atas hak akses grup Odoo.

    Tidak ada baris = tidak ada pembatasan (ikut grup Odoo). Baris hanya dibuat bila ada
    izin yang dicabut lewat matriks Akses User.
    """
    _name = "user.menu.access"
    _description = "Akses User per Menu"
    _order = "user_id, menu_id"

    user_id = fields.Many2one("res.users", required=True, ondelete="cascade", index=True)
    menu_id = fields.Many2one("ir.ui.menu", required=True, ondelete="cascade", index=True)
    can_view = fields.Boolean(string="Lihat", default=True)
    can_create = fields.Boolean(string="Buat", default=True)
    can_write = fields.Boolean(string="Ubah", default=True)
    can_unlink = fields.Boolean(string="Hapus", default=True)
    can_approve = fields.Boolean(string="Setuju", default=True)

    _user_menu_unique = models.Constraint(
        "unique(user_id, menu_id)", "Satu user hanya punya satu baris akses per menu.",
    )

    # ── cache & penegakan ────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env.registry.clear_cache()
        return records

    def write(self, vals):
        result = super().write(vals)
        self.env.registry.clear_cache()
        return result

    def unlink(self):
        result = super().unlink()
        self.env.registry.clear_cache()
        return result

    @api.model
    def _table_ready(self):
        """Tabel belum ada saat modul sedang dipasang / di-upgrade: lewati pembatasan."""
        return table_exists(self.env.cr, self._table)

    @api.model
    @tools.ormcache("self.env.uid")
    def _hidden_menu_ids(self):
        if not self._table_ready():
            return frozenset()
        rows = self.sudo().search([("user_id", "=", self.env.uid), ("can_view", "=", False)])
        hidden = set(rows.menu_id.ids)
        if not hidden:
            return frozenset()
        # Menu induk (aplikasi / folder) yang semua isinya tersembunyi ikut disembunyikan.
        Menu = self.env["ir.ui.menu"]
        visible = Menu._visible_menu_ids(False)
        menus = Menu.sudo().with_context(active_test=False).browse(list(visible))
        children = defaultdict(list)
        for menu in menus:
            children[menu.parent_id.id].append(menu)

        def alive(menu):
            if menu.action:
                return menu.id not in hidden
            return any(alive(child) for child in children[menu.id])

        for menu in menus:
            if not menu.action and not alive(menu):
                hidden.add(menu.id)
        return frozenset(hidden)

    @api.model
    @tools.ormcache("self.env.uid", "mode")
    def _denied_models(self, mode):
        """Model yang ditolak untuk create/write/unlink: semua menu model itu mencabut izinnya."""
        if not self._table_ready():
            return frozenset()
        rows = self.sudo().search([("user_id", "=", self.env.uid)])
        if not rows:
            return frozenset()
        flag = {"create": "can_create", "write": "can_write", "unlink": "can_unlink"}[mode]
        by_menu = {row.menu_id.id: row for row in rows}
        menus_by_model = defaultdict(list)
        for menu in self.env["ir.ui.menu"].sudo().search([("action", "!=", False)]):
            action = menu.action
            if action._name == "ir.actions.act_window" and action.res_model:
                menus_by_model[action.res_model].append(menu.id)
        denied = set()
        for model, menu_ids in menus_by_model.items():
            if all(
                menu_id in by_menu and (not by_menu[menu_id].can_view or not by_menu[menu_id][flag])
                for menu_id in menu_ids
            ):
                denied.add(model)
        return frozenset(denied)

    @api.model
    def has_menu_permission(self, menu_xmlid, perm="approve"):
        """Dipakai kode lain: True bila user boleh `perm` di menu itu (tanpa pembatasan = True)."""
        menu = self.env.ref(menu_xmlid, raise_if_not_found=False)
        if not menu:
            return True
        row = self.sudo().search([("user_id", "=", self.env.uid), ("menu_id", "=", menu.id)], limit=1)
        return True if not row else bool(row[f"can_{perm}"])

    # ── data matriks ─────────────────────────────────────────────────────

    def _check_admin(self):
        if not self.env.user.has_group("base.group_system"):
            raise AccessError("Hanya Administrator yang boleh mengatur akses user.")

    @api.model
    def _collect_leaf_menus(self, user):
        """Menu yang saat ini terlihat oleh user menurut grup Odoo, beserta hak aslinya."""
        Menu = self.env["ir.ui.menu"].with_user(user).with_context(skip_menu_access_filter=True)
        Access = self.env["ir.model.access"].with_user(user).with_context(skip_menu_access_filter=True)
        visible = Menu.search([])._filter_visible_menus().sudo()
        visible_ids = set(visible.ids)
        allowed = {mode: Access._get_allowed_models(mode) for mode in MODEL_MODES}

        leaves = []
        for menu in visible:
            if not menu.action:
                continue
            path = []
            node = menu
            while node:
                path.append(node)
                node = node.parent_id
            path.reverse()
            if len(path) < 2 or any(node.id not in visible_ids for node in path):
                continue
            app, section = path[0], path[1]
            action = menu.action
            model = action.res_model if action._name == "ir.actions.act_window" else False
            # Setuju belum terhubung ke tombol approve mana pun: dikunci di semua menu.
            native = {"view": True, "approve": False}
            na = {"approve": True}
            for perm, mode in MODEL_MODES.items():
                native[perm] = bool(model) and model in allowed[mode]
                na[perm] = not model
            label = menu.name if len(path) <= 3 else f"{path[-2].name} › {menu.name}"
            leaves.append({
                "menu": menu, "app": app, "section": section if len(path) > 2 else False,
                "label": label, "model": model, "native": native, "na": na,
                "order": tuple((node.sequence, node.id) for node in path),
            })
        leaves.sort(key=lambda leaf: leaf["order"])
        return leaves

    @api.model
    def get_matrix(self, user_id):
        self._check_admin()
        user = self.env["res.users"].browse(user_id).exists()
        if not user:
            return {"user": False, "apps": []}
        rows = {row.menu_id.id: row for row in self.sudo().search([("user_id", "=", user.id)])}
        apps = {}
        for leaf in self._collect_leaf_menus(user):
            menu, app = leaf["menu"], leaf["app"]
            row = rows.get(menu.id)
            current = {}
            for perm in PERMS:
                current[perm] = bool(leaf["native"][perm]) and (bool(row[f"can_{perm}"]) if row else True)
            if not current["view"]:
                current = dict.fromkeys(PERMS, False)
            app_data = apps.setdefault(app.id, {"id": app.id, "name": app.name, "sections": {}})
            section_name = leaf["section"].name if leaf["section"] else "Menu"
            section = app_data["sections"].setdefault(section_name, {"name": section_name, "menus": []})
            section["menus"].append({
                "id": menu.id, "name": leaf["label"], "model": leaf["model"] or "",
                "perms": current, "native": leaf["native"], "na": leaf["na"],
            })
        result = []
        for app_data in apps.values():
            app_data["sections"] = list(app_data["sections"].values())
            result.append(app_data)
        return {"user": {"id": user.id, "name": user.name}, "apps": result}

    @api.model
    def save_matrix(self, user_id, rows):
        """rows: [{menu_id, view, create, write, unlink, approve}] untuk semua menu yang tampil."""
        self._check_admin()
        user = self.env["res.users"].browse(user_id).exists()
        if not user:
            return False
        native = {leaf["menu"].id: leaf["native"] for leaf in self._collect_leaf_menus(user)}
        existing = {row.menu_id.id: row for row in self.sudo().search([("user_id", "=", user.id)])}
        Access = self.sudo()
        for item in rows:
            base = native.get(item["menu_id"])
            if base is None:
                continue
            wanted = {perm: bool(item.get(perm)) for perm in PERMS}
            if not wanted["view"]:
                wanted = dict.fromkeys(PERMS, False)
            effective = {perm: base[perm] and wanted[perm] for perm in PERMS}
            restricted = any(base[perm] and not wanted[perm] for perm in PERMS)
            row = existing.get(item["menu_id"])
            if restricted:
                vals = {f"can_{perm}": effective[perm] for perm in PERMS}
                if row:
                    row.write(vals)
                else:
                    Access.create(dict(vals, user_id=user.id, menu_id=item["menu_id"]))
            elif row:
                row.unlink()
        return True

    @api.model
    def reset_matrix(self, user_id):
        self._check_admin()
        self.sudo().search([("user_id", "=", user_id)]).unlink()
        return True

    @api.model
    def get_users(self):
        self._check_admin()
        users = self.env["res.users"].sudo().search([("share", "=", False)], order="name")
        return [{"id": user.id, "name": user.name, "login": user.login} for user in users]
