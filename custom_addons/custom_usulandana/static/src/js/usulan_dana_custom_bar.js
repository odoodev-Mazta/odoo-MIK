/** @odoo-module **/
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState, useEffect } from "@odoo/owl";

export class UsulanUsulanDanaDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.state = useState({ counts: {}, total: 0 });
        onWillStart(async () => { await this.fetchStats(); });
        useEffect(() => { this.fetchStats(); }, () => [this.props.list.records.length]);
    }
    async fetchStats() {
        const data = await this.orm.call("usulan.usulan.dana", "read_group", [[], ['state'], ['state']]);
        let counts = { draft: 0, to_approve: 0, approve: 0, reject: 0, cancel: 0, rilis: 0 };
        let total = 0;
        data.forEach(g => {
            if (counts[g.state] !== undefined) {
                counts[g.state] = g.state_count;
            }
            total += g.state_count;
        });
        this.state.counts = counts;
        this.state.total = total;
    }
    getPercentage(key) {
        if (this.state.total === 0) return 0;
        return Math.round((this.state.counts[key] / this.state.total) * 100);
    }

    setFilter(stateId, stateName) {
        this.env.searchModel.createNewFilters([{
            description: stateName,
            domain: `[('state', '=', '${stateId}')]`,
        }]);
    }

}
UsulanUsulanDanaDashboard.template = "UsulanUsulanDana.Dashboard";
export class UsulanUsulanDanaListController extends ListController {}

UsulanUsulanDanaListController.components = {
    ...ListController.components,
    UsulanUsulanDanaDashboard
};
UsulanUsulanDanaListController.template = "UsulanUsulanDana.ListViewTemplate";

export const usulanUsulanDanaListView = {
    ...listView,
    Controller: UsulanUsulanDanaListController
};
registry.category("views").add("usulan_usulan_dana_list", usulanUsulanDanaListView);