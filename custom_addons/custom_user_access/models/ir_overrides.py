from odoo import models


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    def _filter_visible_menus(self):
        menus = super()._filter_visible_menus()
        if self.env.context.get("skip_menu_access_filter") or self.env.su:
            return menus
        Access = self.env["user.menu.access"]
        granted = Access._granted_menu_ids()
        if granted:
            menus |= self.filtered(lambda menu: menu.id in granted)
        hidden = Access._hidden_menu_ids()
        return menus.filtered(lambda menu: menu.id not in hidden) if hidden else menus


class IrModelAccess(models.Model):
    _inherit = "ir.model.access"

    def _get_allowed_models(self, mode="read"):
        allowed = super()._get_allowed_models(mode)
        if self.env.context.get("skip_menu_access_filter") or self.env.su:
            return allowed
        Access = self.env["user.menu.access"]
        if mode != "read":
            denied = Access._denied_models(mode)
            if denied:
                allowed = allowed - denied
        granted = Access._granted_models(mode)
        return allowed | granted if granted else allowed
