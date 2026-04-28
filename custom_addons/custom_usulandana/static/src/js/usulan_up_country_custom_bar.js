/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState, useEffect } from "@odoo/owl";

export class UsulanUpCountryDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.state = useState({ counts: {}, total: 0 });

        onWillStart(async () => {
            await this.fetchStats();
        });

        // Reaktif jika baris di tabel diubah/dihapus
        useEffect(
            () => {
                if (this.props.list && this.props.list.records) {
                    this.fetchStats();
                }
            },
            () => {
                if (!this.props.list || !this.props.list.records) return [];
                // Pantau perubahan jumlah baris dan perubahan field 'state'
                return [
                    this.props.list.records.length,
                    ...this.props.list.records.map(r => r.data.state)
                ];
            }
        );
    }

    async fetchStats() {
        // Panggil read_group ke backend
        const data = await this.orm.call("usulan.up.country", "read_group", [
            [], // Ambil semua data
            ['state'],
            ['state']
        ]);

        // [UPDATE] Siapkan penampung untuk keenam status
        let counts = {
            draft: 0,
            to_approve: 0,
            approve: 0,
            reject: 0,
            cancel: 0,
            rilis: 0
        };
        let total = 0;

        data.forEach(group => {
            // Cocokkan langsung id state dari database ke object counts
            if (counts[group.state] !== undefined) {
                counts[group.state] += group.state_count;
            }
            total += group.state_count;
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

UsulanUpCountryDashboard.template = "UsulanUpCountry.DashboardTemplate";
UsulanUpCountryDashboard.props = {
    list: { type: Object, optional: true },
    "*": true,
};

export class UsulanUpCountryListController extends ListController {}
UsulanUpCountryListController.components = { ...ListController.components, UsulanUpCountryDashboard };
UsulanUpCountryListController.template = "UsulanUpCountry.ListViewTemplate";

export const usulanUpCountryListView = { ...listView, Controller: UsulanUpCountryListController };
registry.category("views").add("usulan_up_country_list", usulanUpCountryListView);