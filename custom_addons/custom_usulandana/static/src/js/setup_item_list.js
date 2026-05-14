/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState, useEffect } from "@odoo/owl";

export class SetupProgressBar extends Component {
    setup() {
        this.orm = useService("orm");
        this.state = useState({
            waitingCount: 0,
            totalCount: 0,
        });

        onWillStart(async () => {
            await this.fetchProgressData();
        });

        useEffect(
            () => {
                this.fetchProgressData();
            },
            () => {
                if (!this.props.list || !this.props.list.records) return [];

                const dependencies = [this.props.list.records.length];
                for (const record of this.props.list.records) {
                    dependencies.push(record.data.state);
                }
                return dependencies;
            }
        );
    }

    async fetchProgressData() {
        const domainWaiting = [['state', '=', 'waiting']];
        const domainAll = [];

        this.state.waitingCount = await this.orm.searchCount("usulan.dana.setup", domainWaiting);
        this.state.totalCount = await this.orm.searchCount("usulan.dana.setup", domainAll);
    }

    get percentage() {
        if (this.state.totalCount === 0) return 0;
        return Math.round((this.state.waitingCount / this.state.totalCount) * 100);
    }
}

SetupProgressBar.template = "UsulanDana.SetupProgressBar";
SetupProgressBar.props = {
    list: { type: Object, optional: true },
    "*": true,
};

export class SetupItemListController extends ListController {
    setup() {
        super.setup();
    }
}

SetupItemListController.components = {
    ...ListController.components,
    SetupProgressBar,
};

SetupItemListController.template = "UsulanDana.SetupListView";

export const setupItemListView = {
    ...listView,
    Controller: SetupItemListController,
};

registry.category("views").add("setup_item_list", setupItemListView);