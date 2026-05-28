/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class PurchaseRequestTimelineDashboard extends Component {

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            all_pr: [],
            filtered_pr: [],
            departments: [],
            search_query: '',
            selected_dept: '',
        });

        onWillStart(async () => {
            await this.fetchData();
        });
    }

    async fetchData() {
        const [result, departments] = await Promise.all([
            this.orm.call("purchase.request.timeline", "get_dashboard_data", []),
            this.orm.call("purchase.request.timeline", "get_departments", []),
        ]);

        this.state.all_pr = result;
        this.state.filtered_pr = result;
        this.state.departments = departments;
    }

    applyFilters() {
        const q = this.state.search_query.toLowerCase();
        const dept = this.state.selected_dept;

        this.state.filtered_pr = this.state.all_pr.filter(pr => {
            const matchSearch = !q ||
                pr.pr_no.toLowerCase().includes(q) ||
                pr.vendor.toLowerCase().includes(q) ||
                pr.department.toLowerCase().includes(q);
            const matchDept = !dept || String(pr.department_id) === dept;
            return matchSearch && matchDept;
        });
    }

    onSearch(ev) {
        this.state.search_query = ev.target.value;
        this.applyFilters();
    }

    onFilterDept(ev) {
        this.state.selected_dept = ev.target.value;
        this.applyFilters();
    }

    get chartStats() {
        const all = this.state.filtered_pr;
        const total = all.length;
        const complete = all.filter(p => p.status === 'Complete').length;
        const onProgress = all.filter(p => p.status === 'On Progress').length;
        const urgent = all.filter(p => p.is_urgent).length;
        const withPO = all.filter(p => p.po_name !== '-').length;
        return { total, complete, onProgress, urgent, withPO };
    }
}

PurchaseRequestTimelineDashboard.template =
    "custom_purchase_request.PurchaseRequestTimelineTemplate";

registry.category("actions").add(
    "purchase_request_timeline_dashboard",
    PurchaseRequestTimelineDashboard
);