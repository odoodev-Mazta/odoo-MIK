from odoo import models


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    def _filter_visible_menus(self):
        menus = super()._filter_visible_menus()
        if self.env.context.get("skip_menu_access_filter") or self.env.su:
            return menus
        hidden = self.env["user.menu.access"]._hidden_menu_ids()
        return menus.filtered(lambda menu: menu.id not in hidden) if hidden else menus


class IrModelAccess(models.Model):
    _inherit = "ir.model.access"

    def _get_allowed_models(self, mode="read"):
        allowed = super()._get_allowed_models(mode)
        if mode == "read" or self.env.context.get("skip_menu_access_filter") or self.env.su:
            return allowed
        denied = self.env["user.menu.access"]._denied_models(mode)
        return allowed - denied if denied else allowed
