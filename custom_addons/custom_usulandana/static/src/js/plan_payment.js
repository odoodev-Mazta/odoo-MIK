/** @odoo-module **/
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

export class PlanPaymentDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");

        this.state = useState({
            departments: [],
            selectedDept: 'all',
            total: 0,

            counts: {
                'menggantung': 0,
                'plan_payment': 0,
                'reschedule': 0,
                'cancel': 0,
                'rilis': 0
            },

            amounts: {
                'menggantung': 0,
                'plan_payment': 0,
                'reschedule': 0,
                'cancel': 0,
                'rilis': 0
            },

            total_amount_all: 0
        });

        onWillStart(async () => {
            this.state.departments = await this.orm.searchRead("hr.department", [], ["name"]);
            await this.fetchStats();
        });
    }

    async fetchStats() {
        let domain = [];
        if (this.state.selectedDept !== 'all') {
            domain.push(['department_id', '=', parseInt(this.state.selectedDept)]);
        }

        const data = await this.orm.call(
            "usulan.plan.payment",
            "read_group",
            [domain, ['state', 'amount_total:sum'], ['state']]
        );

        const newCounts = { 'menggantung': 0, 'plan_payment': 0, 'reschedule': 0, 'cancel': 0, 'rilis': 0 };
        const newAmounts = { 'menggantung': 0, 'plan_payment': 0, 'reschedule': 0, 'cancel': 0, 'rilis': 0 };
        let newTotalCount = 0;
        let grandTotalAmount = 0;

        data.forEach(group => {
            const st = group.state;

            if (newCounts[st] !== undefined) {
                newCounts[st] = group.state_count;
                newAmounts[st] = group.amount_total || 0;

                newTotalCount += group.state_count;

                if (st !== 'cancel') {
                    grandTotalAmount += (group.amount_total || 0);
                }
            }
        });

        this.state.counts = newCounts;
        this.state.amounts = newAmounts;
        this.state.total = newTotalCount;
        this.state.total_amount_all = grandTotalAmount;
    }

    setFilter(stateId, stateName) {
        let domainString = "";
        let filterLabel = "";

        if (this.state.department_id && this.state.department_id !== 'all') {
            domainString = `[('state', '=', '${stateId}'), ('department_id', '=', ${this.state.department_id})]`;
            filterLabel = `${stateName} (Dept ID: ${this.state.department_id})`;
        } else {
            domainString = `[('state', '=', '${stateId}')]`;
            filterLabel = stateName;
        }

        this.env.searchModel.createNewFilters([{
            description: filterLabel,
            domain: domainString,
        }]);
    }

    async onDepartmentChange(ev) {
        const deptId = ev.target.value;
        this.state.selectedDept = deptId;
        await this.fetchStats();

        if (deptId && deptId !== 'all') {
            const deptName = ev.target.options[ev.target.selectedIndex].text;
            this.env.searchModel.createNewFilters([{
                description: `Departemen: ${deptName}`,
                domain: `[('department_id', '=', ${deptId})]`,
            }]);
        } else {
            // Jika pilih 'all', tidak usah buat filter baru
        }
    }

    getPercentage(stateName) {
        const count = this.state.counts[stateName] || 0;
        if (this.state.total === 0) return 0;
        return (count / this.state.total) * 100;
    }

    getBarColor(stateName) {
        const colors = {
            'menggantung': 'bg-warning',
            'plan_payment': 'bg-info',
            'reschedule': 'bg-danger',
            'cancel': 'bg-dark',
            'rilis': 'bg-success'
        };
        return colors[stateName] || 'bg-primary';
    }
}
PlanPaymentDashboard.template = "UsulanDana.PlanPaymentDashboard";


export class PlanPaymentListController extends ListController {
    setup() {
        super.setup();
    }
}
PlanPaymentListController.components = {
    ...ListController.components,
    PlanPaymentDashboard,
};
PlanPaymentListController.template = "UsulanDana.PlanPaymentListView";


export const planPaymentDashboardListView = {
    ...listView,
    Controller: PlanPaymentListController,
};

registry.category("views").add("plan_payment_dashboard_list", planPaymentDashboardListView);