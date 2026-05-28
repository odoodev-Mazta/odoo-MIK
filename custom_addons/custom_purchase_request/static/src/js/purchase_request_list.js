/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart } from "@odoo/owl";

class PurchaseRequestDashboard extends Component {
    static template = "custom_purchase_request.PurchaseRequestDashboard";
    static props = ["onDeptChange"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            departments: [],
            selectedDeptId: false,
            totalPR: 0,
        });

        onWillStart(async () => {
            await this._loadDepartments();
            await this._loadTotal();
        });
    }

    async _loadDepartments() {
        const records = await this.orm.searchRead(
            "purchase.request",
            [],
            ["department_id"]
        );
        const seen = new Set();
        const departments = [];
        for (const rec of records) {
            if (rec.department_id && !seen.has(rec.department_id[0])) {
                seen.add(rec.department_id[0]);
                departments.push({ id: rec.department_id[0], name: rec.department_id[1] });
            }
        }
        this.state.departments = departments;
    }

    async _loadTotal() {
        const domain = this.state.selectedDeptId
            ? [["department_id", "=", this.state.selectedDeptId]]
            : [];
        this.state.totalPR = await this.orm.searchCount("purchase.request", domain);
    }

    async onChangeDepartment(ev) {
        const val = ev.target.value;
        this.state.selectedDeptId = val ? parseInt(val) : false;
        await this._loadTotal();
        this.props.onDeptChange(this.state.selectedDeptId);
    }
}

class PurchaseRequestListController extends ListController {
    static template = "custom_purchase_request.ListView";
    static components = {
        ...ListController.components,
        PurchaseRequestDashboard,
    };

    onDeptChange(deptId) {
        const domain = deptId ? [["department_id", "=", deptId]] : [];
        this.env.searchModel.createNewFilters([
            {
                description: "Department",
                domain: domain,
                type: "filter",
            },
        ]);
    }
}

registry.category("views").add("purchase_request_list", {
    ...listView,
    Controller: PurchaseRequestListController,
});