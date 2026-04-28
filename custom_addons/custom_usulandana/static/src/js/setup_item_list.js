/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { useService } from "@web/core/utils/hooks";
// [UPDATE] Tambahkan useEffect di baris import ini
import { Component, onWillStart, useState, useEffect } from "@odoo/owl";

export class SetupProgressBar extends Component {
    setup() {
        this.orm = useService("orm");
        this.state = useState({
            waitingCount: 0,
            totalCount: 0,
        });

        // Fetch data pertama kali saat dimuat
        onWillStart(async () => {
            await this.fetchProgressData();
        });

        // [BARU] Pantau perubahan tabel secara real-time
        useEffect(
            () => {
                this.fetchProgressData();
            },
            () => {
                // Cek apakah tabel sudah memuat data
                if (!this.props.list || !this.props.list.records) return [];

                // Jadikan jumlah baris dan status tiap baris sebagai pemicu (trigger).
                // Jika ada record dihapus (length berubah) atau diubah statusnya, useEffect akan jalan.
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
// [BARU] Izinkan OWL untuk menerima props "list" dari XML
SetupProgressBar.props = {
    list: { type: Object, optional: true },
    "*": true, // Izinkan props bawaan Odoo lainnya
};

// 2. Ekstensi ListController untuk mendaftarkan Component
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

// 3. Daftarkan custom view ke Odoo Registry
export const setupItemListView = {
    ...listView,
    Controller: SetupItemListController,
};

registry.category("views").add("setup_item_list", setupItemListView);