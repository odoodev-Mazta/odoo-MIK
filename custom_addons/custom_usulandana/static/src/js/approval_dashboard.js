/** @odoo-module **/
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState, useEffect } from "@odoo/owl";

export class ApprovalDanaDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.state = useState({
            departments: [],
            selectedDept: 'all',
            counts: {},
            total: 0
        });

        onWillStart(async () => {
            this.state.departments = await this.orm.searchRead("hr.department", [], ["name"]);
            await this.fetchStats();
        });

        useEffect(() => { this.fetchStats(); }, () => [this.props.list.records.length]);
    }

    async fetchStats() {
        let domain = [];
        if (this.state.selectedDept !== 'all') {
            domain.push(['department_id', '=', parseInt(this.state.selectedDept)]);
        }

        const data = await this.orm.call(
            "usulan.dana.approval",
            "read_group",
            [
                domain,
                ['state'],
                ['state']
            ]
        );

        const newCounts = {};
        let newTotal = 0;
        data.forEach(group => {
            newCounts[group.state] = group.state_count;
            newTotal += group.state_count;
        });

        this.state.counts = newCounts;
        this.state.total = newTotal;
    }

    async onDepartmentChange(ev) {
        this.state.selectedDept = ev.target.value;
        await this.fetchStats();

        if (this.state.selectedDept !== 'all') {
            const deptName = ev.target.options[ev.target.selectedIndex].text;
            this.env.searchModel.createNewFilters([{
                description: `Departemen: ${deptName}`,
                domain: `[('department_id', '=', ${parseInt(this.state.selectedDept)})]`,
            }]);
        } else {
            this.env.searchModel.createNewFilters([]);
        }
    }

    setFilter(stateId, stateName) {
        let domainString = "";
        let filterLabel = "";

        if (this.state.selectedDept && this.state.selectedDept !== 'all') {
            domainString = `[('state', '=', '${stateId}'), ('department_id', '=', ${this.state.selectedDept})]`;
            filterLabel = `${stateName} (Terfilter Dept)`;
        } else {
            domainString = `[('state', '=', '${stateId}')]`;
            filterLabel = stateName;
        }

        this.env.searchModel.createNewFilters([{
            description: filterLabel,
            domain: domainString,
        }]);
    }

    getPercentage(status) {
        if (this.state.total === 0) return 0;
        return ((this.state.counts[status] || 0) / this.state.total) * 100;
    }

    getBarColor(status) {
        const colors = {
            'to_approve': 'bg-warning',
            'approve': 'bg-success',
            'reject': 'bg-danger',
            'cancel': 'bg-secondary'
        };
        return colors[status];
    }
}
ApprovalDanaDashboard.template = "UsulanDana.ApprovalDanaDashboard";

export class ApprovalListController extends ListController {}
ApprovalListController.components = { ...ListController.components, ApprovalDanaDashboard };
ApprovalListController.template = "UsulanDana.ApprovalListView";

export const approvalListView = { ...listView, Controller: ApprovalListController };
registry.category("views").add("approval_dashboard_list", approvalListView);