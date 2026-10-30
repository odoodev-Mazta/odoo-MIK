/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, useState } from "@odoo/owl";

const STATE_CONFIG = [
    { key: "draft",              label: "Draft",                icon: "fa-file-o",        color: "#6c757d" },
    { key: "progress",           label: "On Progress",          icon: "fa-pencil",        color: "#0d6efd" },
    { key: "approval_marketing", label: "Approval Marketing",   icon: "fa-bullhorn",      color: "#fd7e14" },
    { key: "approval_client",    label: "Approval Client",      icon: "fa-user-circle",   color: "#6610f2" },
    { key: "approval_ro",        label: "Approval RO",          icon: "fa-shield",        color: "#0dcaf0" },
    { key: "upload_form",        label: "Upload Form Design",   icon: "fa-upload",        color: "#198754" },
    { key: "done",               label: "Done",                 icon: "fa-check-circle",  color: "#20c997" },
    { key: "reject",             label: "Rejected",             icon: "fa-times-circle",  color: "#dc3545" },
];

export class DesignApprovalDashboard extends Component {
    static template = "custom_design.DesignApprovalDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            counts: {},
            total: 0,
            done_pct: 0,
            stateConfig: STATE_CONFIG,
        });
        onMounted(() => this.loadData());
    }

    async loadData() {
        const data = await this.orm.call("design.usulan", "get_dashboard_data", []);
        this.state.counts = data.counts || {};
        this.state.total = data.total || 0;
        this.state.done_pct = data.done_pct || 0;
        this.state.loading = false;
    }

    openState(stateKey) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Usulan Design",
            res_model: "design.usulan",
            view_mode: "list,form",
            domain: stateKey ? [["state", "=", stateKey]] : [],
            views: [[false, "list"], [false, "form"]],
        });
    }

    get progressBarWidth() {
        return Math.min(this.state.done_pct, 100) + "%";
    }
}

registry.category("actions").add("design_approval_dashboard", DesignApprovalDashboard);
