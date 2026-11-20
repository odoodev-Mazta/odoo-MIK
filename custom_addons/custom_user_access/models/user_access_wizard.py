from odoo import Command, api, fields, models
from odoo.exceptions import AccessError


class UserAccessWizard(models.TransientModel):
    _name = "user.access.wizard"
    _description = "Akses User"

    user_id = fields.Many2one(
        "res.users", string="User", required=True, domain=[("share", "=", False)],
    )
    line_ids = fields.One2many("user.access.wizard.line", "wizard_id", string="Akses per Modul")

    @api.onchange("user_id")
    def _onchange_user_id(self):
        self.line_ids = [Command.clear()]
        if not self.user_id:
            return
        privileges = self.env["res.groups.privilege"].sudo().search([("group_ids", "!=", False)])
        # Rapi per kategori (A-Z), lalu per modul (A-Z) di dalam kategorinya.
        privileges = privileges.sorted(key=lambda p: ((p.category_id.name or "zzz").lower(), (p.name or "").lower()))
        lines = []
        for privilege in privileges:
            current = privilege.group_ids & self.user_id.sudo().group_ids
            lines.append(Command.create({
                "privilege_id": privilege.id,
                "group_ids": [Command.set(current.ids)],
                "current_group_ids": [Command.set(current.ids)],
            }))
        self.line_ids = lines

    def action_apply(self):
        """Simpan akses: hanya modul yang diubah yang ditulis ke user."""
        self.ensure_one()
        if not self.env.user.has_group("base.group_system"):
            raise AccessError("Hanya Administrator yang boleh mengatur akses user.")
        user = self.user_id.sudo()
        changed = []
        for line in self.line_ids:
            if set(line.group_ids.ids) == set(line.current_group_ids.ids):
                continue
            all_groups = line.privilege_id.sudo().group_ids
            user.write({"group_ids": [Command.unlink(g.id) for g in all_groups]
                                     + [Command.link(g.id) for g in line.group_ids]})
            changed.append(line.privilege_id.name)
            line.current_group_ids = [Command.set(line.group_ids.ids)]
        message = (
            f"Akses {user.name} diperbarui: {', '.join(changed)}." if changed else "Tidak ada perubahan akses."
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": "Akses User", "message": message, "type": "success", "sticky": False},
        }


class UserAccessWizardLine(models.TransientModel):
    _name = "user.access.wizard.line"
    _description = "Akses User per Modul"
    _order = "id"

    wizard_id = fields.Many2one("user.access.wizard", required=True, ondelete="cascade")
    privilege_id = fields.Many2one("res.groups.privilege", string="Modul", required=True, readonly=True)
    category_id = fields.Many2one(related="privilege_id.category_id", string="Kategori", readonly=True)
    group_ids = fields.Many2many(
        "res.groups", "user_access_line_group_rel", "line_id", "group_id", string="Akses",
        help="Kosongkan bila user tidak boleh memakai modul ini.",
    )
    current_group_ids = fields.Many2many(
        "res.groups", "user_access_line_current_rel", "line_id", "group_id", string="Akses Saat Ini",
    )
    available_group_ids = fields.Many2many(
        "res.groups", compute="_compute_available_group_ids", string="Pilihan Akses",
    )

    @api.depends("privilege_id")
    def _compute_available_group_ids(self):
        for line in self:
            line.available_group_ids = line.privilege_id.sudo().group_ids
