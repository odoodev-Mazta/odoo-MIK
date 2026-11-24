/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const PERMS = ["view", "create", "write", "unlink", "approve"];
const COLUMNS = [
    { key: "view", label: "Lihat", icon: "fa-eye" },
    { key: "create", label: "Buat", icon: "fa-plus" },
    { key: "write", label: "Ubah", icon: "fa-pencil" },
    { key: "unlink", label: "Hapus", icon: "fa-trash" },
    { key: "approve", label: "Setuju", icon: "fa-check-circle-o" },
];

export class AccessMatrix extends Component {
    static template = "custom_user_access.AccessMatrix";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.columns = COLUMNS;
        this.state = useState({
            users: [],
            userId: false,
            apps: [],
            appId: false,
            search: "",
            dirty: false,
            loading: false,
        });
        onWillStart(async () => {
            this.state.users = await this.orm.call("user.menu.access", "get_users", []);
        });
    }

    // ── data ────────────────────────────────────────────────────────────

    async onUserChange(ev) {
        this.state.userId = parseInt(ev.target.value) || false;
        await this.loadMatrix();
    }

    async loadMatrix() {
        if (!this.state.userId) {
            this.state.apps = [];
            this.state.appId = false;
            return;
        }
        this.state.loading = true;
        const data = await this.orm.call("user.menu.access", "get_matrix", [this.state.userId]);
        this.state.apps = data.apps;
        const keep = this.state.apps.find((app) => app.id === this.state.appId);
        this.state.appId = keep ? keep.id : (this.state.apps[0] && this.state.apps[0].id) || false;
        this.state.dirty = false;
        this.state.loading = false;
    }

    get currentApp() {
        return this.state.apps.find((app) => app.id === this.state.appId);
    }

    get visibleSections() {
        const app = this.currentApp;
        if (!app) {
            return [];
        }
        const term = this.state.search.trim().toLowerCase();
        return app.sections
            .map((section) => ({
                name: section.name,
                menus: section.menus.filter(
                    (menu) => !term || menu.name.toLowerCase().includes(term) || section.name.toLowerCase().includes(term)
                ),
            }))
            .filter((section) => section.menus.length);
    }

    activeCount(app) {
        let count = 0;
        for (const section of app.sections) {
            for (const menu of section.menus) {
                if (menu.perms.view) {
                    count++;
                }
            }
        }
        return count;
    }

    // ── interaksi ───────────────────────────────────────────────────────

    isLocked(menu, perm) {
        return !!(menu.na && menu.na[perm]);
    }

    toggle(menu, perm) {
        if (this.isLocked(menu, perm)) {
            return;
        }
        this._set(menu, perm, !menu.perms[perm]);
        this.state.dirty = true;
    }

    _set(menu, perm, value) {
        menu.perms[perm] = value;
        if (perm === "view" && !value) {
            for (const other of PERMS) {
                menu.perms[other] = false;
            }
        } else if (perm !== "view" && value) {
            menu.perms.view = true;
        }
    }

    columnState(perm) {
        const cells = [];
        for (const section of this.visibleSections) {
            for (const menu of section.menus) {
                if (!this.isLocked(menu, perm)) {
                    cells.push(menu.perms[perm]);
                }
            }
        }
        return cells.length > 0 && cells.every(Boolean);
    }

    toggleColumn(perm) {
        const value = !this.columnState(perm);
        for (const section of this.visibleSections) {
            for (const menu of section.menus) {
                if (!this.isLocked(menu, perm)) {
                    this._set(menu, perm, value);
                }
            }
        }
        this.state.dirty = true;
    }

    selectApp(appId) {
        this.state.appId = appId;
        this.state.search = "";
    }

    async save() {
        const rows = [];
        for (const app of this.state.apps) {
            for (const section of app.sections) {
                for (const menu of section.menus) {
                    rows.push({ menu_id: menu.id, ...menu.perms });
                }
            }
        }
        await this.orm.call("user.menu.access", "save_matrix", [this.state.userId, rows]);
        this.notification.add("Akses user disimpan. Minta user memuat ulang halaman (Ctrl+Shift+R).", {
            type: "success",
        });
        await this.loadMatrix();
    }

    async reset() {
        await this.orm.call("user.menu.access", "reset_matrix", [this.state.userId]);
        this.notification.add("Semua pembatasan akses user dihapus.", { type: "success" });
        await this.loadMatrix();
    }
}

registry.category("actions").add("custom_user_access.matrix", AccessMatrix);
